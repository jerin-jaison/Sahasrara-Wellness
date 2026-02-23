"""
Session helper for multi-step booking flow.

Booking session structure stored in request.session['booking']:
{
    "branch_id":    "<uuid>",
    "service_id":   "<uuid>",
    "worker_id":    "<uuid> | 'any'",
    "booking_date": "YYYY-MM-DD",
    "start_time":   "HH:MM",
    "slot_lock_id": "<uuid>",
    "guest_id":     "<uuid>",
    "booking_id":   "<uuid>",
    "guest_name":   "...",
    "guest_phone":  "...",
    "guest_email":  "...",
}

Use the helpers below instead of accessing session['booking'] directly.
"""
SESSION_KEY = 'booking'

# Keys that represent step completion checkpoints
STEP_KEYS = {
    1: 'branch_id',
    2: 'service_id',
    3: 'worker_id',
    4: 'booking_date',
    5: 'start_time',
    6: 'guest_phone',
    7: 'slot_lock_id',
}


def get_booking_session(request: object) -> dict:
    return request.session.get(SESSION_KEY, {})


def set_booking_session(request: object, data: dict) -> None:
    session = request.session.get(SESSION_KEY, {})
    session.update(data)
    request.session[SESSION_KEY] = session
    request.session.modified = True


def clear_booking_session(request: object) -> None:
    request.session.pop(SESSION_KEY, None)
    request.session.modified = True


def booking_session_get(request: object, key: str, default=None):
    return get_booking_session(request).get(key, default)


def step_is_complete(request: object, step: int) -> bool:
    """Returns True if all required keys up to `step` are present in session."""
    session = get_booking_session(request)
    for s in range(1, step + 1):
        if STEP_KEYS.get(s) and not session.get(STEP_KEYS[s]):
            return False
    return True
