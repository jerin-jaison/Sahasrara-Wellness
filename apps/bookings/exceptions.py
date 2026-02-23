"""
Custom exceptions for the booking engine.
Raised in engine.py and caught in views.py for clean error handling.
"""


class BookingEngineError(Exception):
    """Base exception for all booking engine errors."""
    pass


class SlotConflictError(BookingEngineError):
    """Raised when a CONFIRMED booking already exists for the requested slot."""
    pass


class SlotAlreadyLockedException(BookingEngineError):
    """Raised when an active (non-expired) SlotLock exists for the requested slot."""
    pass


class WorkerNotAvailableError(BookingEngineError):
    """Raised when the selected worker has no schedule or is on leave for the date."""
    pass


class NoWorkersAvailableError(BookingEngineError):
    """Raised when 'Any Worker' is selected but no workers are available for the slot."""
    pass


class SameDayCutoffError(BookingEngineError):
    """Raised when a same-day booking is attempted within the 2-hour cutoff window."""
    pass


class InvalidSlotError(BookingEngineError):
    """Raised when the requested start_time does not fall within valid slot boundaries."""
    pass
