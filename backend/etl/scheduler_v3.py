from update_observations_v3 import update_database


if __name__ == "__main__":
    print("Running scheduled update...")
    update_database()
    print("Update complete.")