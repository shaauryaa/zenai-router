from evaluation.check_data import FILES, check_file, check_leakage, load


def test_data_files_have_only_allowed_labels():
    problems = []
    for name, text_col, domain_col, action_col in FILES:
        problems += check_file(name, load(name), text_col, domain_col, action_col)
    assert problems == []


def test_no_test_text_in_training_files():
    frames = {name: (load(name), text_col) for name, text_col, _, _ in FILES}
    assert check_leakage(frames) == []
