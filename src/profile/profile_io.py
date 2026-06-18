import json
from pathlib import Path
from src.schemas.user_profile import UserProfile
import warnings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CV_FOLDER_PATH = PROJECT_ROOT / "user_files" / "CVs"
DATA_PATH = PROJECT_ROOT / "src" / "profile" / "profile_data.json"

SUPPORTED_CV_EXTENSIONS = {".pdf", ".docx", ".txt", ".doc"}


def pick_cv() -> Path | None:
    if not CV_FOLDER_PATH.exists():
        raise FileNotFoundError(f"CV folder not found at {CV_FOLDER_PATH}")

    cvs = [f for f in CV_FOLDER_PATH.iterdir() if f.suffix.lower() in SUPPORTED_CV_EXTENSIONS]

    if not cvs:
        warnings.warn(f"No files with expected extensions ({', '.join(SUPPORTED_CV_EXTENSIONS)}) found in CV folder at {CV_FOLDER_PATH}.")
        return None

    if len(cvs) == 1:
        return cvs[0] #if there's only one CV, just use it without asking. Otherwise, ask the user to pick one.

    print("Multiple CVs found. Pick one:")
    for i, cv in enumerate(cvs, 1):
        print(f"  [{i}] {cv.name}")

    while True:
        try:
            choice = input(f"Enter number (1-{len(cvs)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(cvs):
                return cvs[idx]
        except ValueError:
            pass
        print(f"Invalid choice. Enter 1-{len(cvs)}.")


def create_profile_from_cv(cv_path: Path) -> UserProfile:
    from src.tools.doc_reader import read_document
    cv_text = read_document(cv_path)
    return UserProfile(cv_text=cv_text)


def load_profile() -> UserProfile:
    if not DATA_PATH.exists():
        warnings.warn(f"No existing profile found at {DATA_PATH}. Checking for CV ...")
        cv = pick_cv()
        if cv:
            return create_profile_from_cv(cv)
        return UserProfile()

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return UserProfile.model_validate(data)


def save_profile(profile: UserProfile) -> None:
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(profile.model_dump(mode="json"), f, indent=2, ensure_ascii=False)


def update_profile(updates: dict) -> UserProfile:
    profile = load_profile()
    profile = profile.model_copy(update=updates, deep=True)
    save_profile(profile)
    return profile


def reset_profile() -> None:
    if DATA_PATH.exists():
        DATA_PATH.unlink()
        print(f"Deleted {DATA_PATH}")
    else:
        print("No profile data to reset.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manage your job seeker profile.")
    parser.add_argument("--reset", action="store_true", help="Delete saved profile data")
    parser.add_argument("--show", action="store_true", help="Load and display current profile")
    parser.add_argument("--pick-cv", action="store_true", help="Test CV file selection")
    parser.add_argument("--create-from-cv", type=str, default=None, help="Create and save profile from a specific CV file")
    parser.add_argument("--create-from-cv-dir", action="store_true", help="Pick a CV from the folder and create a profile")
    parser.add_argument("--create-from-text", type=str, default=None, help="Create and save profile from raw text")
    parser.add_argument("--update", type=str, default=None, help="Update profile fields. JSON string, e.g. '{\"skills\": [\"Python\"]}'")
    args = parser.parse_args()

    if args.reset:
        reset_profile()
    elif args.show:
        profile = load_profile()
        print(profile.model_dump_json(indent=2))
    elif args.pick_cv:
        cv = pick_cv()
        if cv:
            print(f"Selected CV: {cv}")
    elif args.create_from_cv:
        from src.tools.doc_reader import read_document
        cv_text = read_document(args.create_from_cv)
        profile = UserProfile(cv_text=cv_text)
        save_profile(profile)
        print("Profile created and saved from CV:")
        print(profile.model_dump_json(indent=2))
    elif args.create_from_cv_dir:
        cv = pick_cv()
        if not cv:
            print("No CV selected. Aborting.")
        else:
            profile = create_profile_from_cv(cv)
            save_profile(profile)
            print("Profile created and saved from CV:")
            print(profile.model_dump_json(indent=2))
    elif args.create_from_text:
        profile = UserProfile(cv_text=args.create_from_text)
        save_profile(profile)
        print("Profile created and saved from text:")
        print(profile.model_dump_json(indent=2))
    elif args.update:
        updates = json.loads(args.update)
        profile = update_profile(updates)
        print("Updated profile:")
        print(profile.model_dump_json(indent=2))
    else:
        parser.print_help()
