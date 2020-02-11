import os, sys, inspect
import git
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)
import Constants.constants as cst
from DatabaseDriver.UpstreamPatchTable import UpstreamPatchTable
from UpstreamTracker.MonitorChanges import parse_maintainers, sanitize_filenames
from Util.util import list_diff


def get_symbols(files):
    """
    get_symbols: This function returns a list of symbols for given files
    files: HyperV files list
    @return symbol_list: list of symbols generated through ctags
    """
    command = "ctags -x −−c−kinds=f -R "+files+" | awk '{ if ($2 == \"function\") print $1 }' "+cst.RedirectOp+"../tmp.txt"
    # print("[Info] Running command: "+command)
    os.system(command)
    symbol_list = [line.rstrip('\n') for line in open('../tmp.txt')]
    return symbol_list


def map_symbols_to_patch(commits, fileNames, prev_commit="097c1bd5673edaf2a162724636858b71f658fdd2"):
    """
    This function generates and stores symbols generated by each patch
    prev_commit : SHA of start of HyperV patchTo track symbols generated by current patch we compare symbols generated
    by last commit to this commit symbols.
    commits: SHA of all commits in database
    fileNames: hyperV files
    """
    up = UpstreamPatchTable()
    os.chdir(os.path.join(cst.PATH_TO_REPOS, cst.LINUX_SYMBOL_REPO_NAME))
    command = "git reset --hard "+prev_commit
    print("[Info] "+command)
    os.system(command)
    before_patch_apply = None
    # iterate
    for commit in commits:
        # get symbols
        if before_patch_apply is None:
            before_patch_apply = get_symbols(' '.join(fileNames))

        command = "git reset --hard "+commit
        os.system(command)
        # get symbols
        after_patch_apply = get_symbols(' '.join(fileNames))

        # compare
        diff_symbols = list_diff(after_patch_apply, before_patch_apply)
        print("Commit:"+commit+" -> "+''.join(diff_symbols))

        # save symbols into database
        up.save_patch_symbols(commit, ' '.join(diff_symbols))
        before_patch_apply = after_patch_apply

    print("[Info] Finished symbol tracker")


def get_hyperv_patch_symbols():
    """
    This function clones upstream and gets upstream commits, hyperV files
    """
    up = UpstreamPatchTable()
    commits = up.get_commits()

    path_to_linux = os.path.join(cst.PATH_TO_REPOS, cst.LINUX_SYMBOL_REPO_NAME)
    if os.path.exists(path_to_linux):
        print("[Info] Path to Linux Repo exists")
        repo = git.Repo(path_to_linux)
        print("[Info] Fetching recent changes")
        repo.git.fetch()
    else:
        print("[Info] Path to Linux repo does not exists. Cloning linux repo.")
        git.Git(cst.PATH_TO_REPOS).clone("https://github.com/torvalds/linux.git", cst.LINUX_SYMBOL_REPO_NAME)
        repo = git.Repo(path_to_linux)
    print("[Info] parsing maintainers files")
    fileList = parse_maintainers(repo)
    print("[Info] Received HyperV file paths")
    filenames = sanitize_filenames(fileList)
    print("[Info] Preprocessed HyperV file paths")
    map_symbols_to_patch(commits, filenames)


def symbol_checker(symbol_file):
    """
    This function returns missing symbols by comparing database patch symbols with given symbols
    symbol_file: file containing symbols to run against database
    return missing_symbols_patch: list of missing symbols from given list
    """
    print("[Info] Starting Symbol Checker")
    list_of_symbols = [line.strip() for line in open(symbol_file)]
    up = UpstreamPatchTable()
    symbol_map = up.get_patch_symbols()
    missing_symbol_patch = []
    for patchId, symbols in symbol_map.items():
        if len(list_diff(symbols, list_of_symbols)) > 0:
            missing_symbol_patch.append(patchId)
    return sorted(missing_symbol_patch)


if __name__ == '__main__':
    print("[Info] Starting Symbol matcher")
    get_hyperv_patch_symbols()
    missing_symbols = symbol_checker("../syms.txt")
    print("Missing symbols")
    print(*missing_symbols)
