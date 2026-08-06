import winsound


def play_wake_tone():
    winsound.MessageBeep(
        winsound.MB_OK
    )