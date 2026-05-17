def serialise_time(time_in_seconds: int, return_hour: bool = True) -> str:
    """Serialise time in seconds as string in HH:MM:SS or MM:SS format.

    Args:
        time_in_seconds (int): number of seconds to serialise.
        return_hour (bool): calculate number of hours if true, else leave time
          in MM:SS format.

    Returns:
        time in string format HH:MM:SS or MM:SS.
    """
    minutes, seconds = divmod(time_in_seconds, 60)

    if return_hour:
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    return f"{minutes:02d}:{seconds:02d}"
