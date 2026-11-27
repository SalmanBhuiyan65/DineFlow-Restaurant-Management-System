"""Domain services for Best-Fit Seating and Waitlist management (Member 2: Orin)."""

from bookings_menu.models import DiningTable, WaitlistEntry


def find_best_fit_table(party_size):
    """Find the smallest empty DiningTable that fits ``party_size``.

    Args:
        party_size: Positive integer number of guests.

    Returns:
        The best-fitting ``DiningTable`` instance, or ``None`` if no
        empty table has sufficient capacity.
    """
    if party_size <= 0:
        return None
    return (
        DiningTable.objects.filter(
            status=DiningTable.STATUS_EMPTY,
            capacity__gte=party_size,
        )
        .order_by('capacity', 'code')
        .first()
    )


def assign_waitlist_best_fit(entry):
    """Attempt to assign a waiting party to the best-fit empty table.

    Args:
        entry: ``WaitlistEntry`` instance in ``waiting`` status.

    Returns:
        The assigned ``DiningTable`` if seated, otherwise ``None``.
    """
    if entry.status != WaitlistEntry.STATUS_WAITING:
        return None
    table = find_best_fit_table(entry.party_size)
    if table is None:
        return None
    entry.assigned_table = table
    entry.status = WaitlistEntry.STATUS_SEATED
    entry.save(update_fields=['assigned_table', 'status'])
    table.status = DiningTable.STATUS_ORDERING
    table.save(update_fields=['status'])
    return table
