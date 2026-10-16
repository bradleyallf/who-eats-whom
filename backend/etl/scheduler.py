from update_observations import update_database


if __name__ == "__main__":
    print("Running scheduled update...")
    update_database()
    print("Update complete.")