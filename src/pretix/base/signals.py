import warnings
from typing import Any, Callable, List, Tuple

import django.dispatch
from django.apps import apps
from django.conf import settings
from django.dispatch.dispatcher import NO_RECEIVERS

from .models import Event

app_cache = {}


def _populate_app_cache():
    global app_cache
    apps.check_apps_ready()
    for ac in apps.app_configs.values():
        app_cache[ac.name] = ac


class EventPluginSignal(django.dispatch.Signal):
    """
    This is an extension to Django's built-in signals which differs in a way that it sends
    out it's events only to receivers which belong to plugins that are enabled for the given
    Event.
    """

    def send(self, sender: Event, **named) -> List[Tuple[Callable, Any]]:
        """
        Send signal from sender to all connected receivers that belong to
        plugins enabled for the given Event.

        sender is required to be an instance of ``pretix.base.models.Event``.
        """
        if sender and not isinstance(sender, Event):
            raise ValueError("Sender needs to be an event.")

        responses = []
        if not self.receivers or self.sender_receivers_cache.get(sender) is NO_RECEIVERS:
            return responses

        if not app_cache:
            _populate_app_cache()

        for receiver in self._live_receivers(sender):
            # Find the Django application this belongs to
            searchpath = receiver.__module__
            core_module = any([searchpath.startswith(cm) for cm in settings.CORE_MODULES])
            app = None
            if not core_module:
                while True:
                    app = app_cache.get(searchpath)
                    if "." not in searchpath or app:
                        break
                    searchpath, _ = searchpath.rsplit(".", 1)

            # Only fire receivers from active plugins and core modules
            if core_module or (sender and app and app.name in sender.get_plugins()):
                if not hasattr(app, 'compatibility_errors') or not app.compatibility_errors:
                    response = receiver(signal=self, sender=sender, **named)
                    responses.append((receiver, response))
        return sorted(responses, key=lambda r: (receiver.__module__, receiver.__name__))


class DeprecatedSignal(django.dispatch.Signal):

    def connect(self, receiver, sender=None, weak=True, dispatch_uid=None):
        warnings.warn('This signal is deprecated and will soon be removed', stacklevel=3)
        super().connect(receiver, sender=None, weak=True, dispatch_uid=None)


event_live_issues = EventPluginSignal(
    providing_args=[]
)
"""
This signal is sent out to determine whether an event can be taken live. If you want to
prevent the event from going live, return a string that will be displayed to the user
as the error message. If you don't, your receiver should return ``None``.

As with all event-plugin signals, the ``sender`` keyword argument will contain the event.
"""


register_payment_providers = EventPluginSignal(
    providing_args=[]
)
"""
This signal is sent out to get all known payment providers. Receivers should return a
subclass of pretix.base.payment.BasePaymentProvider

As with all event-plugin signals, the ``sender`` keyword argument will contain the event.
"""

register_invoice_renderers = EventPluginSignal(
    providing_args=[]
)
"""
This signal is sent out to get all known invoice renderers. Receivers should return a
subclass of pretix.base.invoice.BaseInvoiceRenderer

As with all event-plugin signals, the ``sender`` keyword argument will contain the event.
"""

register_ticket_outputs = EventPluginSignal(
    providing_args=[]
)
"""
This signal is sent out to get all known ticket outputs. Receivers should return a
subclass of pretix.base.ticketoutput.BaseTicketOutput

As with all event-plugin signals, the ``sender`` keyword argument will contain the event.
"""

register_data_exporters = EventPluginSignal(
    providing_args=[]
)
"""
This signal is sent out to get all known data exporters. Receivers should return a
subclass of pretix.base.exporter.BaseExporter

As with all event-plugin signals, the ``sender`` keyword argument will contain the event.
"""

validate_cart = EventPluginSignal(
    providing_args=["positions"]
)
"""
This signal is sent out before the user starts checkout. It includes an iterable
with the current CartPosition objects.
The response of receivers will be ignored, but you can raise a CartError with an
appropriate exception message.

As with all event-plugin signals, the ``sender`` keyword argument will contain the event.
"""

order_placed = EventPluginSignal(
    providing_args=["order"]
)
"""
This signal is sent out every time an order is placed. The order object is given
as the first argument.

As with all event-plugin signals, the ``sender`` keyword argument will contain the event.
"""

order_paid = EventPluginSignal(
    providing_args=["order"]
)
"""
This signal is sent out every time an order is paid. The order object is given
as the first argument.

As with all event-plugin signals, the ``sender`` keyword argument will contain the event.
"""

logentry_display = EventPluginSignal(
    providing_args=["logentry"]
)
"""
To display an instance of the ``LogEntry`` model to a human user,
``pretix.base.signals.logentry_display`` will be sent out with a ``logentry`` argument.

The first received response that is not ``None`` will be used to display the log entry
to the user. The receivers are expected to return plain text.

As with all event-plugin signals, the ``sender`` keyword argument will contain the event.
"""

logentry_object_link = EventPluginSignal(
    providing_args=["logentry"]
)
"""
To display the relationship of an instance of the ``LogEntry`` model to another model
to a human user, ``pretix.base.signals.logentry_object_link`` will be sent out with a
``logentry`` argument.

The first received response that is not ``None`` will be used to display the related object
to the user. The receivers are expected to return a HTML link. The internal implementation
builds the links like this::

    a_text = _('Tax rule {val}')
    a_map = {
        'href': reverse('control:event.settings.tax.edit', kwargs={
            'event': sender.slug,
            'organizer': sender.organizer.slug,
            'rule': logentry.content_object.id
        }),
        'val': escape(logentry.content_object.name),
    }
    a_map['val'] = '<a href="{href}">{val}</a>'.format_map(a_map)
    return a_text.format_map(a_map)

Make sure that any user content in the HTML code you return is properly escaped!
As with all event-plugin signals, the ``sender`` keyword argument will contain the event.
"""

requiredaction_display = EventPluginSignal(
    providing_args=["action", "request"]
)
"""
To display an instance of the ``RequiredAction`` model to a human user,
``pretix.base.signals.requiredaction_display`` will be sent out with a ``action`` argument.
You will also get the current ``request`` in a different argument.

The first received response that is not ``None`` will be used to display the log entry
to the user. The receivers are expected to return HTML code.

As with all event-plugin signals, the ``sender`` keyword argument will contain the event.
"""

event_copy_data = EventPluginSignal(
    providing_args=["other"]
)
"""
This signal is sent out when a new event is created as a clone of an existing event, i.e.
the settings from the older event are copied to the newer one. You can listen to this
signal to copy data or configuration stored within your plugin's models as well.

You don't need to copy data inside the general settings storage which is cloned automatically,
but you might need to modify that data.

The ``sender`` keyword argument will contain the event of the **new** event. The ``other``
keyword argument will contain the event to **copy from**.
"""

periodic_task = django.dispatch.Signal()
"""
This is a regular django signal (no pretix event signal) that we send out every
time the periodic task cronjob runs. This interval is not sharply defined, it can
be everything between a minute and a day. The actions you perform should be
idempotent, i.e. it should not make a difference if this is sent out more often
than expected.
"""

register_global_settings = django.dispatch.Signal()
"""
All plugins that are installed may send fields for the global settings form, as
an OrderedDict of (setting name, form field).
"""

order_fee_calculation = EventPluginSignal(
    providing_args=['request']
)
"""
This signals allows you to add fees to an order while it is being created. You are expected to
return a list of ``OrderFee`` objects that are not yet saved to the database
(because there is no order yet).

As with all plugin signals, the ``sender`` keyword argument will contain the event. A ``positions``
argument will contain the cart positions and ``invoice_address`` the invoice address (useful for
tax calculation). The argument ``meta_info`` contains the order's meta dictionary.
"""
