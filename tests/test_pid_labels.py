from utils.pid_labels import pick_launched_pid


def test_single_new_pid_returned():
    assert pick_launched_pid({1, 2}, {1, 2, 3}, assigned=set()) == 3


def test_no_new_pid_returns_none():
    assert pick_launched_pid({1, 2}, {1, 2}, assigned=set()) is None


def test_two_new_pids_is_ambiguous_returns_none():
    assert pick_launched_pid({1}, {1, 2, 3}, assigned=set()) is None


def test_new_pid_already_assigned_is_excluded():
    # 3 appeared but is already owned by another account -> not a candidate
    assert pick_launched_pid({1, 2}, {1, 2, 3}, assigned={3}) is None


def test_assigned_pid_excluded_leaving_one_candidate():
    # 3 already assigned, 4 is the genuinely new one
    assert pick_launched_pid({1, 2}, {1, 2, 3, 4}, assigned={3}) == 4
