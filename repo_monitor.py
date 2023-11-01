import os
import shelve

from conf import MONITORED_REPOS


def read_commit_log(repo, local_path, on_new_commit):
    os.system(f"cd {local_path} && git log --oneline > commit_log.txt")

    with open(f"{local_path}/commit_log.txt", "r") as f:
        with shelve.open(f"{local_path}/commit_log") as db:
            for line in reversed(f.readlines()):
                key = line[0:9]
                value = line[10:]
                if key not in db:
                    db[key] = value
                    on_new_commit(repo, value)


def check_repos(on_new_commit):
    print("Checking repos...")
    for repo, path in MONITORED_REPOS.items():
        local_path = path.split("/")[-1][:-4]
        if not os.path.exists(local_path):
            os.system(f"git clone --filter=blob:none --no-checkout {path}")
            read_commit_log(repo, local_path, lambda *args: None)

        os.system(f"cd {local_path} && git fetch --filter=blob:none")
        read_commit_log(repo, local_path, on_new_commit)


if __name__ == "__main__":
    check_repos(print)
