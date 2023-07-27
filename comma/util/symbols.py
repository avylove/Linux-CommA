# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
"""
Functions for generating symbol maps
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from comma.database.model import PatchData


if TYPE_CHECKING:
    from comma.cli import Session


LOGGER = logging.getLogger(__name__)


def get_symbols(repo_dir, files):
    """
    Returns a set of symbols for given files
    files: iterable of files
    returns set of symbols generated through ctags
    """
    command = "ctags -R -x −−c−kinds=f {}".format(
        " ".join(files) + " | awk '{ if ($2 == \"function\") print $1 }'"
    )
    LOGGER.debug("Running command: %s", command)
    process = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        cwd=repo_dir,
        check=True,
        universal_newlines=True,
    )
    return set(process.stdout.splitlines())


class Symbols:
    """
    Parent object for symbol operations
    """

    def __init__(self, session: Session, repo) -> None:
        self.config = session.config
        self.database = session.database
        self.repo = repo
        self.session = session

    def get_missing_commits(self, symbol_file):
        """Returns a sorted list of commit IDs whose symbols are missing from the given file"""

        LOGGER.info("Starting Symbol Checker")
        self.get_patch_symbols()
        LOGGER.info("Detecting missing symbols")
        return self.symbol_checker(symbol_file)

    def get_patch_symbols(self):
        """
        This function clones upstream and gets upstream commits
        """

        with self.database.get_session() as session:
            # SQLAlchemy returns tuples which need to be unwrapped
            self.map_symbols_to_patch(
                [
                    commit[0]
                    for commit in session.query(PatchData.commitID)
                    .order_by(PatchData.commitTime)
                    .all()
                ],
                self.session.get_tracked_paths(),
            )

    # TODO (Issue 65): Avoid hard-coding commit ID
    def map_symbols_to_patch(
        self, commits: Iterable[str], paths, prev_commit="097c1bd5673edaf2a162724636858b71f658fdd2"
    ):
        """
        This function generates and stores symbols generated by each patch
        repo: git repo object
        files: hyperV files
        commits: SHA of all commits in database
        prev_commit: SHA of start of HyperV patch to track
        """

        LOGGER.info("Mapping symbols to commits")

        # Preserve initial reference
        initial_reference = self.repo.head.reference

        try:
            self.repo.checkout(prev_commit)
            before_patch_apply = None

            # Iterate through commits
            for commit in commits:
                # Get symbols before patch is applied
                if before_patch_apply is None:
                    before_patch_apply = get_symbols(self.repo.working_tree_dir, paths)

                # Checkout commit
                self.repo.checkout(commit)

                # Get symbols after patch is applied
                after_patch_apply = get_symbols(self.repo.working_tree_dir, paths)

                # Compare symbols before and after patch
                diff_symbols = after_patch_apply - before_patch_apply
                if diff_symbols:
                    print(f"Commit: {commit} -> {' '.join(diff_symbols)}")

                # Save symbols to database
                with self.database.get_session() as session:
                    patch = session.query(PatchData).filter_by(commitID=commit).one()
                    patch.symbols = " ".join(diff_symbols)

                # Use symbols from current commit to compare to next commit
                before_patch_apply = after_patch_apply

        finally:
            # Reset reference
            self.repo.checkout(initial_reference)

    def symbol_checker(self, file_path: Path):
        """
        This function returns missing symbols by comparing database patch symbols with given symbols
        file_path: file containing symbols to run against database
        returns sorted list of commits whose symbols are missing from file
        """
        with open(file_path, "r", encoding="utf-8") as symbol_file:
            symbols_in_file = {line.strip() for line in symbol_file}

        with self.database.get_session() as session:
            return sorted(
                commitID
                for commitID, symbols in session.query(PatchData.commitID, PatchData.symbols)
                .filter(PatchData.symbols != " ")
                .order_by(PatchData.commitTime)
                .all()
                if len(set(symbols.split(" ")) - symbols_in_file) > 0
            )
