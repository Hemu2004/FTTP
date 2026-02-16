
class SimulationResult:
    def __init__(self, labour_teams, equipment_units, total_days):
        self.labour_teams = labour_teams
        self.equipment_units = equipment_units
        self.total_days = total_days

def simulate_network(distance, premises):
    labour = int(premises / 12 + distance / 120)
    equipment = int(distance / 250)
    total_days = int(distance / 80 + premises / 30)
    return SimulationResult(labour, equipment, total_days)
