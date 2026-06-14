if __name__ == "__main__":
    try:
        number_of_floors = int(input("Enter Number of Floors: "))
        number_of_elevators = int(input("Enter Number of Elevators: "))

        if number_of_floors <= 0:
            raise ValueError("Number of floors must be greater than 0")

        if number_of_elevators <= 0:
            raise ValueError("Number of elevators must be greater than 0")

        building = Building(
            number_of_floors=number_of_floors,
            number_of_lifts=number_of_elevators,
            total_energy=10000.0
        )

        building.display_status()

    except ValueError as e:
        print(f"Error: {e}")