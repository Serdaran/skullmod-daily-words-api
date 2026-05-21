import argparse
import csv
import secrets
import sys
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings
from app.db import engine, init_db
from app.models import PhysicalSkull


def next_artifact_number(session: Session) -> int:
    artifacts = session.exec(select(PhysicalSkull)).all()
    max_number = 0

    for artifact in artifacts:
        _, _, suffix = artifact.artifact_code.partition("-")
        if suffix.isdigit():
            max_number = max(max_number, int(suffix))

    return max_number + 1


def unique_token(session: Session, field_name: str) -> str:
    while True:
        token = secrets.token_urlsafe(32)
        field = getattr(PhysicalSkull, field_name)
        existing = session.exec(select(PhysicalSkull).where(field == token)).first()
        if not existing:
            return token


def build_certificate_code(artifact_code: str) -> str:
    return f"CERT-{artifact_code}"


def create_artifacts(
    count: int,
    production_batch: Optional[str],
    artifact_type: Optional[str],
    artifact_series: Optional[str],
    material_type: Optional[str],
    visual_theme: Optional[str],
    base_url: str,
    output_path: Path,
) -> None:
    init_db()
    rows = []

    with Session(engine) as session:
        next_number = next_artifact_number(session)

        for offset in range(count):
            artifact_code = f"SKM-{next_number + offset:06d}"
            public_token = unique_token(session, "public_token")
            claim_token = unique_token(session, "claim_token")

            artifact = PhysicalSkull(
                artifact_code=artifact_code,
                public_token=public_token,
                claim_token=claim_token,
                production_batch=production_batch,
                artifact_type=artifact_type,
                artifact_series=artifact_series,
                material_type=material_type,
                visual_theme=visual_theme,
                certificate_code=build_certificate_code(artifact_code),
            )
            session.add(artifact)
            rows.append(
                {
                    "artifact_code": artifact_code,
                    "nfc_url": f"{base_url.rstrip('/')}/nfc/{public_token}",
                    "public_token": public_token,
                    "claim_token": claim_token,
                    "claim_status": "unclaimed",
                    "production_batch": production_batch or "",
                    "artifact_type": artifact_type or "",
                    "artifact_series": artifact_series or "",
                    "material_type": material_type or "",
                    "visual_theme": visual_theme or "",
                    "certificate_code": artifact.certificate_code or "",
                }
            )

        session.commit()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Created {count} SkullMod artifacts.")
    print(f"CSV: {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create physical SkullMod artifact records and NFC URL CSV output."
    )
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--production-batch", default=None)
    parser.add_argument("--artifact-type", default="prototype")
    parser.add_argument("--artifact-series", default=None)
    parser.add_argument("--material-type", default=None)
    parser.add_argument("--visual-theme", default=None)
    parser.add_argument("--base-url", default=settings.PUBLIC_NFC_BASE_URL)
    parser.add_argument(
        "--output",
        default="exports/physical_skull_artifacts.csv",
        help="CSV output path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.count < 1:
        raise SystemExit("--count must be at least 1")

    create_artifacts(
        count=args.count,
        production_batch=args.production_batch,
        artifact_type=args.artifact_type,
        artifact_series=args.artifact_series,
        material_type=args.material_type,
        visual_theme=args.visual_theme,
        base_url=args.base_url,
        output_path=Path(args.output),
    )


if __name__ == "__main__":
    main()
