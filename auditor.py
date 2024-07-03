"""
Audits PyPI to determine if the contents included in the wheel for each version of a given release match those of the
GitHub release.
"""

import os
import pathlib
import subprocess
import sys
from typing import Optional, Union
from zipfile import ZipFile

import requests


# default tmp dirs
ZIP_CHECK_DIR = "/tmp/zip_check"
GH_DIR = f"{ZIP_CHECK_DIR}/gh"
PYPI_DIR = f"{ZIP_CHECK_DIR}/pypi"


class Auditor:
    def __init__(self, pypi_name: str, gh_name: str, download_path: Optional[str] = ZIP_CHECK_DIR):
        """
        Main class for the auditor.
        :param pypi_name: the name of the pypi package
        :param gh_name: the 'creator/package' name of the GitHub repository
        :param download_path: the filepath to download the files for comparison. By default, it is in the /tmp directory
        """
        self.gh_path = pathlib.Path(download_path, "gh")
        self.pypi_path = pathlib.Path(download_path, "pypi")
        self.gh_repo = gh_name
        self.pypi_package = pypi_name

        # creates file paths if they do not currently exist
        pathlib.Path(download_path).mkdir(exist_ok=True)
        pathlib.Path(self.gh_path).mkdir(exist_ok=True)
        pathlib.Path(self.pypi_path).mkdir(exist_ok=True)

    def compare_zip_files(self, pypi_downloaded_file, gh_downloaded_file) -> list[dict[str, Union[str, list]]]:
        """
        Compares two files, and returns a list of the differences between them. Does this on a line-by-line basis of
        the files contained within each zip.
        :param pypi_downloaded_file: the filepath for the downloaded file from PyPI
        :param gh_downloaded_file: the filepath for the downloaded file from GitHub
        :return: List of the differences (if any) between the two files.
        """
        with ZipFile(pypi_downloaded_file, 'r') as zip1, ZipFile(gh_downloaded_file, 'r') as zip2:
            # Ensure paths are normalized by stripping 'bittensor/' and any leading directory names
            def normalize_path(path):
                if f"{self.pypi_package}/" in path:
                    return '/'.join(path.split(f'{self.pypi_package}/')[1:])
                return None

            zip1_files = {
                normalize_path(name): zip1.read(name).decode('utf-8')
                for name in zip1.namelist()
                if normalize_path(name) is not None
            }
            zip2_files = {
                normalize_path(name): zip2.read(name).decode('utf-8')
                for name in zip2.namelist()
                if normalize_path(name) is not None
            }

            all_files = set(zip1_files.keys()).union(zip2_files.keys())
            differences = []

            for file in all_files:
                file1_lines = zip1_files.get(file, "").splitlines()
                file2_lines = zip2_files.get(file, "").splitlines()

                if file1_lines != file2_lines:
                    diff = {
                        'file': file,
                        'differences': [(i + 1, line1, line2) for i, (line1, line2) in
                                        enumerate(zip(file1_lines, file2_lines)) if line1 != line2]
                    }
                    if len(file1_lines) != len(file2_lines):
                        longer = file1_lines if len(file1_lines) > len(file2_lines) else file2_lines
                        diff['differences'].extend(
                            [(i + 1, line, '') for i, line in enumerate(longer[len(file1_lines):], start=len(file1_lines))])

                    differences.append(diff)

            return differences

    def pip_download(self, package_version: str) -> bool:
        """
        Downloads the wheel from PyPI using installed pip
        :param package_version: the specified version of the package
        """
        command = [
            sys.executable, '-m', 'pip', 'download', "--no-deps", f"{self.pypi_package}=={package_version}",
            "--dest", self.pypi_path
        ]

        result = subprocess.run(command, text=True, capture_output=True)

        if result.returncode == 0:
            lines = result.stdout.splitlines()
            for line in lines:
                if "Saved" in line:
                    filename = line.split()[-1]
                    os.rename(
                        filename, f"{self.pypi_path}/{package_version}"
                    )
            return True
        else:
            return False

    def get_available_versions(self) -> list[str]:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'index', 'versions', self.pypi_package],
            text=True,
            capture_output=True
        )

        if result.returncode == 0:
            return [x.strip() for x in result.stdout[37:].split(",")]
        else:
            raise ValueError(f"Failed to retrieve versions. {result.stderr}")

    def gh_download(self, package_version: str) -> bool:
        """
        Downloads the release from GitHub, according to the specified version.
        :param package_version: the version of the package to download.
        """
        gh_link = f"https://github.com/{self.gh_repo}/archive/refs/tags/v{package_version}.zip"
        result = requests.get(gh_link)
        if result.status_code == 200:
            with open(f"{self.gh_path}/{package_version}", "wb+") as fp:
                fp.write(result.content)
            return True
        else:
            return False

    def run(self, verbose=True):
        all_versions = self.get_available_versions()
        all_differences = []
        for version in all_versions:
            pip_download = self.pip_download(version)
            gh_download = self.gh_download(version)
            if pip_download and gh_download:
                comparison = self.compare_zip_files(
                    pathlib.Path(self.pypi_path, version),
                    pathlib.Path(self.gh_path, version),
                )
                if comparison:
                    all_differences.append(comparison)
                    if verbose:
                        print(f"{version} error: {comparison}")
                else:
                    if verbose:
                        print(f"{version} OK")
            else:
                if verbose:
                    print(f"{version} skipped: PyPI {pip_download}; GH {gh_download}")


if __name__ == "__main__":
    auditor = Auditor(
        "bittensor",
        "opentensor/bittensor"
    )
    auditor.run()
