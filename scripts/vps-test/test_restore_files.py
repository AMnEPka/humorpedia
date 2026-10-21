import hashlib
import json
import os
import tarfile
import tempfile
import unittest
from pathlib import Path

from restore_files import extract_verified


def make_archive(path, members):
    with tarfile.open(path, "w:gz") as archive:
        for name, kind, payload in members:
            info = tarfile.TarInfo(name)
            if kind == "dir":
                info.type = tarfile.DIRTYPE
                info.mode = 0o700
                archive.addfile(info)
            elif kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = payload
                archive.addfile(info)
            elif kind == "hardlink":
                info.type = tarfile.LNKTYPE
                info.linkname = payload
                archive.addfile(info)
            elif kind == "fifo":
                info.type = tarfile.FIFOTYPE
                archive.addfile(info)
            else:
                data = payload
                info.size = len(data)
                info.mode = 0o600
                import io
                archive.addfile(info, io.BytesIO(data))


class RestoreFilesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="humorpedia-r5-restore-")
        self.root = Path(self.tmp.name)
        self.archive = self.root / "media.tar.gz"

    def tearDown(self):
        self.tmp.cleanup()

    def test_restores_private_zip_and_media_bytes_with_verified_hash(self):
        zip_bytes = b"private package bytes"
        image_bytes = b"image bytes"
        make_archive(self.archive, [
            ("page-packages", "dir", b""),
            ("page-packages/pkg-123.zip", "file", zip_bytes),
            ("uploads/photo.bin", "file", image_bytes),
            ("page-packages-manifest.json", "file", json.dumps({
                "page-packages/pkg-123.zip": hashlib.sha256(zip_bytes).hexdigest()
            }).encode("utf-8")),
        ])
        target = self.root / "data"

        extract_verified(self.archive, target)

        self.assertEqual((target / "page-packages/pkg-123.zip").read_bytes(), zip_bytes)
        self.assertEqual((target / "uploads/photo.bin").read_bytes(), image_bytes)

    def test_rejects_traversal_before_writing_outside_target(self):
        make_archive(self.archive, [("../outside.txt", "file", b"escape")])
        target = self.root / "data"

        with self.assertRaises((ValueError, OSError)):
            extract_verified(self.archive, target)

        self.assertFalse((self.root / "outside.txt").exists())

    def test_rejects_absolute_and_unlisted_paths(self):
        for name in ("/tmp/escape.txt", "C:/outside.txt", "uploads\\outside.txt", "secrets/key.txt"):
            with self.subTest(name=name):
                make_archive(self.archive, [(name, "file", b"x")])
                with self.assertRaises((ValueError, OSError)):
                    extract_verified(self.archive, self.root / "data")

    def test_rejects_duplicate_or_noncanonical_member_paths(self):
        cases = [
            [("uploads/photo.bin", "file", b"one"), ("uploads/photo.bin", "file", b"two")],
            [("uploads//photo.bin", "file", b"bad")],
            [("uploads/", "dir", b""), ("uploads", "dir", b"")],
        ]
        for members in cases:
            with self.subTest(members=members):
                make_archive(self.archive, members)
                target = self.root / "data"
                with self.assertRaises((ValueError, OSError)):
                    extract_verified(self.archive, target)
                self.assertFalse(target.exists())

    def test_rejects_symlink_hardlink_and_nonregular_members(self):
        cases = [
            ("uploads/link", "symlink", "../../outside"),
            ("uploads/hard", "hardlink", "uploads/photo"),
            ("uploads/pipe", "fifo", b""),
        ]
        for member in cases:
            with self.subTest(member=member):
                make_archive(self.archive, [member])
                with self.assertRaises((ValueError, OSError)):
                    extract_verified(self.archive, self.root / "data")

    def test_rejects_hash_mismatch_and_existing_file_without_overwrite(self):
        make_archive(self.archive, [
            ("page-packages/pkg.zip", "file", b"original"),
            ("page-packages-manifest.json", "file", json.dumps({"page-packages/pkg.zip": "0" * 64}).encode("utf-8")),
        ])
        target = self.root / "data"
        with self.assertRaises((ValueError, OSError)):
            extract_verified(self.archive, target)
        self.assertFalse(target.exists())

        make_archive(self.archive, [
            ("page-packages/pkg.zip", "file", b"original"),
            ("page-packages-manifest.json", "file", json.dumps({
                "page-packages/pkg.zip": hashlib.sha256(b"original").hexdigest()
            }).encode("utf-8")),
        ])
        destination = target / "page-packages/pkg.zip"
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"keep")
        with self.assertRaises((ValueError, OSError)):
            extract_verified(self.archive, target)
        self.assertEqual(destination.read_bytes(), b"keep")

    def test_rejects_manifest_missing_or_extra_private_file(self):
        for entries in ({}, {"page-packages/other.zip": hashlib.sha256(b"x").hexdigest()}):
            with self.subTest(entries=entries):
                make_archive(self.archive, [
                    ("page-packages/pkg.zip", "file", b"zip"),
                    ("page-packages-manifest.json", "file", json.dumps(entries).encode("utf-8")),
                ])
                with self.assertRaises((ValueError, OSError)):
                    extract_verified(self.archive, self.root / "data")

    def test_restores_legacy_media_archive_without_private_manifest(self):
        make_archive(self.archive, [("uploads/photo.bin", "file", b"legacy")])
        target = self.root / "data"

        extract_verified(self.archive, target)

        self.assertEqual((target / "uploads/photo.bin").read_bytes(), b"legacy")

    def test_rejects_private_file_without_manifest(self):
        make_archive(self.archive, [("page-packages/pkg.zip", "file", b"zip")])
        with self.assertRaises((ValueError, OSError)):
            extract_verified(self.archive, self.root / "data")

    def test_rejects_symlinked_target_parent_before_writing_outside_target(self):
        make_archive(self.archive, [("uploads/photo.bin", "file", b"escape")])
        target = self.root / "data"
        outside = self.root / "outside"
        outside.mkdir()
        target.mkdir()
        try:
            os.symlink(outside, target / "uploads", target_is_directory=True)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"Symlink creation is unavailable in this test environment: {error}")

        with self.assertRaises((ValueError, OSError)):
            extract_verified(self.archive, target)

        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
