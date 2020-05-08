import logging
import os
import xml.etree.ElementTree as ET

import git

import Util.Constants as cst


class DatabaseCredentials:
    def __init__(self):
        secret_repo_path = os.path.join(cst.PATH_TO_REPOS, cst.SECRET_REPO_NAME)
        if os.path.exists(secret_repo_path):
            logging.info("Path to Secrets Repo exists")
            repo = git.Repo(secret_repo_path)
            logging.debug("Pulling recent changes for secrets repo")
            repo.remotes.origin.pull()
            logging.info("Git pull complete")
        else:
            logging.debug("Path to Secrets repo does not exists")
            logging.info("Cloning Secrets repo")
            db_cred_environ_name = "LSG_SECRET_DB_CRED"
            db_cred = os.getenv(db_cred_environ_name)
            if db_cred is None:
                logging.error(
                    "Please set %s environment variable as your token to access LSG-Secret repo."
                    % db_cred_environ_name
                )
                raise Exception(
                    "LSG-Secret Repo token not set in environment variale: %s"
                    % db_cred_environ_name
                )
            git.Git(cst.PATH_TO_REPOS).clone(
                "https://anything:%s@<redacted>"
                % db_cred
            )
            logging.info("Cloning Complete")
        tree = ET.parse(os.path.join(secret_repo_path, "PatchTrackerSecrets.xml"))
        root = tree.getroot()
        self.database_server = root.find("DatabaseServer").text
        self.database_name = root.find("DatabaseName").text
        self.database_user = root.find("DatabaseUser").text
        self.database_password = root.find("DatabasePassword").text
