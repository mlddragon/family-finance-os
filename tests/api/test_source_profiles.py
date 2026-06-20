from dillon_finances.source_profiles import get_source_profile, list_source_profiles


def test_source_profile_registry_contains_approved_v1_sources():
    profiles = list_source_profiles()
    profile_keys = {profile.source_key for profile in profiles}

    assert profile_keys == {
        "alliant_checking",
        "alliant_savings",
        "alliant_credit_card",
        "chase_prime_visa",
    }


def test_source_profiles_include_import_contract_fields():
    profile = get_source_profile("chase_prime_visa")

    assert profile.display_name == "Chase Prime Visa"
    assert profile.account_type == "credit_card"
    assert profile.required is True
    assert profile.freshness_threshold_days == 14
    assert ".csv" in profile.accepted_file_extensions
    assert profile.expected_headers
    assert profile.amount_sign_policy
    assert profile.parser_version == "chase_prime_visa:v1"
