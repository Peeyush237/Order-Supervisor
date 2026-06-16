"""Shared domain constants: business actions, event types, terminal events."""

# The 5 required business actions. Each writes an activity record (kind="action");
# none send anything externally.
BUSINESS_ACTIONS = [
    "message_fulfillment_team",
    "message_payments_team",
    "message_logistics_team",
    "message_customer",
    "create_internal_note",
]

# Event types the generator/simulator can inject as signals.
EVENT_TYPES = [
    "order_created",
    "payment_confirmed",
    "payment_failed",
    "shipment_created",
    "shipment_delayed",
    "delivered",
    "refund_requested",
    "customer_message_received",
    "no_update_for_n_hours",
]

# Events that, when they arrive, satisfy a workflow-owned completion rule.
# (The agent only *recommends* completion; the workflow ends on these.)
TERMINAL_EVENTS = {"delivered"}

# Default classifier priority map: which events are important enough to wake the
# main agent immediately vs. be recorded and deferred to the next scheduled wake.
HIGH_PRIORITY_EVENTS = {
    "payment_failed",
    "shipment_delayed",
    "refund_requested",
    "customer_message_received",
    "delivered",
    "order_created",
}
LOW_PRIORITY_EVENTS = {
    "payment_confirmed",
    "shipment_created",
    "no_update_for_n_hours",
}
