import json
from pathlib import Path
from src.schemas.user_profile import UserProfile
from src.tools.doc_reader import SUPPORTED_EXTENSIONS, read_document
import warnings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CV_FOLDER_PATH = PROJECT_ROOT / "user_files" / "CVs"
COVER_LETTER_FOLDER_PATH = PROJECT_ROOT / "user_files" / "CoverLetters"
DATA_PATH = PROJECT_ROOT / "src" / "profile" / "profile_data.json"


def _pick_file(folder: Path, label: str) -> Path | None:
    if not folder.exists():
        raise FileNotFoundError(f"{label} folder not found at {folder}")

    files = [f for f in folder.iterdir() if f.suffix.lower() in SUPPORTED_EXTENSIONS]

    if not files:
        warnings.warn(f"No supported files found in {label} folder at {folder}.")
        return None

    if len(files) == 1:
        return files[0]

    print(f"Multiple {label}s found. Pick one:")
    for i, f in enumerate(files, 1):
        print(f"  [{i}] {f.name}")

    while True:
        try:
            choice = input(f"Enter number (1-{len(files)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(files):
                return files[idx]
        except ValueError:
            pass
        print(f"Invalid choice. Enter 1-{len(files)}.")


def pick_cv() -> Path | None:
    return _pick_file(CV_FOLDER_PATH, "CV")


def pick_cover_letter() -> Path | None:
    return _pick_file(COVER_LETTER_FOLDER_PATH, "cover letter")


def create_profile(cv_path: Path | None = None, cover_letter_path: Path | None = None) -> UserProfile:
    kwargs = {}
    if cv_path:
        kwargs["cv_text"] = read_document(cv_path)
    if cover_letter_path:
        kwargs["cover_letter_text"] = read_document(cover_letter_path)

    return UserProfile(**kwargs)


def create_profile_from_cv(cv_path: Path) -> UserProfile:
    return create_profile(cv_path=cv_path)


def create_profile_from_cover_letter(cover_letter_path: Path) -> UserProfile:
    return create_profile(cover_letter_path=cover_letter_path)


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
    parser.add_argument("--pick-cover-letter", action="store_true", help="Test cover letter file selection")
    parser.add_argument("--create-from-cv", type=str, default=None, help="Create and save profile from a specific CV file")
    parser.add_argument("--create-from-cv-dir", action="store_true", help="Pick a CV from the folder and create a profile")
    parser.add_argument("--create-from-cover-letter", type=str, default=None, help="Create and save profile from a specific cover letter file")
    parser.add_argument("--create-from-cover-letter-dir", action="store_true", help="Pick a cover letter from the folder and create a profile")
    parser.add_argument("--create-from-both", type=str, nargs=2, metavar=("CV_PATH", "CL_PATH"), default=None, help="Create profile from both a CV file and a cover letter file")
    parser.add_argument("--create-from-user-files", action="store_true", help="Pick both a CV and a cover letter from their folders")
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
    elif args.pick_cover_letter:
        cl = pick_cover_letter()
        if cl:
            print(f"Selected cover letter: {cl}")
    elif args.create_from_cv:
        profile = create_profile(cv_path=Path(args.create_from_cv))
        save_profile(profile)
        print("Profile created and saved from CV:")
        print(profile.model_dump_json(indent=2))
    elif args.create_from_cv_dir:
        cv = pick_cv()
        if not cv:
            print("No CV selected. Aborting.")
        else:
            profile = create_profile(cv_path=cv)
            save_profile(profile)
            print("Profile created and saved from CV:")
            print(profile.model_dump_json(indent=2))
    elif args.create_from_cover_letter:
        profile = create_profile(cover_letter_path=Path(args.create_from_cover_letter))
        save_profile(profile)
        print("Profile created and saved from cover letter:")
        print(profile.model_dump_json(indent=2))
    elif args.create_from_cover_letter_dir:
        cl = pick_cover_letter()
        if not cl:
            print("No cover letter selected. Aborting.")
        else:
            profile = create_profile(cover_letter_path=cl)
            save_profile(profile)
            print("Profile created and saved from cover letter:")
            print(profile.model_dump_json(indent=2))
    elif args.create_from_both:
        cv_path, cl_path = [Path(p) for p in args.create_from_both]
        profile = create_profile(cv_path=cv_path, cover_letter_path=cl_path)
        save_profile(profile)
        print("Profile created and saved from CV and cover letter:")
        print(profile.model_dump_json(indent=2))
    elif args.create_from_user_files:
        cv = pick_cv()
        cl = pick_cover_letter()
        if not cv and not cl:
            print("No CV or cover letter selected. Aborting.")
        else:
            profile = create_profile(cv_path=cv, cover_letter_path=cl)
            save_profile(profile)
            print("Profile created and saved:")
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
