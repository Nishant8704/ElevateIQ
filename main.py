import tkinter as tk
import time
import csv
import os
import threading
import winsound  # Only works on Windows

class Request:
    def __init__(self, floor, direction, timestamp, target, passengers=1):
        self.floor = floor
        self.direction = direction
        self.timestamp = timestamp
        self.target = target
        self.passengers = passengers

class Lift:
    def __init__(self, lift_id, total_floors):
        self.lift_id = lift_id
        self.current_floor = 0
        self.direction = "IDLE"
        self.pickup_requests = []
        self.drop_requests = []
        self.last_move_time = time.time()
        self.load = 0
        self.total_floors = total_floors

    def add_request(self, floor, direction, target, passengers=1):
        self.pickup_requests.append(Request(floor, direction, time.time(), target, passengers))

    def get_wait_time_priority(self, r):
        return time.time() - r.timestamp

    def update(self):
        now = time.time()
        if now - self.last_move_time < 1:
            return

        # Drop off passengers
        if self.current_floor in self.drop_requests:
            self.drop_requests.remove(self.current_floor)
            self.load = max(0, self.load - 1)
            winsound.Beep(800, 200)

        # Pick up waiting passengers
        for r in self.pickup_requests[:]:
            if r.floor == self.current_floor:
                self.pickup_requests.remove(r)
                self.drop_requests.append(r.target)
                self.load += r.passengers
                winsound.Beep(600, 200)

        # Pickup window logic (2-floor range)
        window_requests = []
        for r in self.pickup_requests:
            if self.direction == "UP" and self.current_floor < r.floor <= self.current_floor + 2 and r.direction == "UP":
                window_requests.append(r)
            elif self.direction == "DOWN" and self.current_floor - 2 <= r.floor < self.current_floor and r.direction == "DOWN":
                window_requests.append(r)

        for r in window_requests:
            if r.floor not in self.drop_requests:
                self.drop_requests.append(r.floor)

        # Decide next movement
        if not self.pickup_requests and not self.drop_requests:
            self.direction = "IDLE"
        else:
            all_targets = [r.floor for r in self.pickup_requests] + self.drop_requests
            if self.direction == "UP":
                valid = [f for f in all_targets if f >= self.current_floor]
                next_floor = min(valid or all_targets, key=lambda f: abs(f - self.current_floor))
            elif self.direction == "DOWN":
                valid = [f for f in all_targets if f <= self.current_floor]
                next_floor = max(valid or all_targets, key=lambda f: abs(f - self.current_floor))
            else:
                next_floor = min(all_targets, key=lambda f: abs(f - self.current_floor))

            if next_floor > self.current_floor:
                self.direction = "UP"
                self.current_floor += 1
            elif next_floor < self.current_floor:
                self.direction = "DOWN"
                self.current_floor -= 1
            else:
                self.direction = "IDLE"

        self.last_move_time = now

class LiftSimulator:
    def __init__(self, root):
        self.root = root
        self.canvas = tk.Canvas(root, width=600, height=600)
        self.canvas.pack()
        self.floor_height = 50
        self.run_simulation = False
        self.stats = []
        self.lifts = []
        self.floors = 10
        self.num_lifts = 2
        self.create_config_ui()
        self.log_file = "lift_logs.csv"
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "From", "To", "Direction", "Lift", "Passengers"])

    def create_config_ui(self):
        self.root.title("Smart Lift Simulator")
        frame = tk.Frame(self.root)
        frame.pack()

        tk.Label(frame, text="Number of Floors:").grid(row=0, column=0)
        self.floor_entry = tk.Entry(frame)
        self.floor_entry.insert(0, "10")
        self.floor_entry.grid(row=0, column=1)

        tk.Label(frame, text="Number of Lifts:").grid(row=0, column=2)
        self.lift_entry = tk.Entry(frame)
        self.lift_entry.insert(0, "2")
        self.lift_entry.grid(row=0, column=3)

        tk.Button(frame, text="Start Simulation", command=self.start_simulation).grid(row=0, column=4)

    def start_simulation(self):
        self.floors = int(self.floor_entry.get())
        self.num_lifts = int(self.lift_entry.get())
        self.lifts = [Lift(i, self.floors) for i in range(self.num_lifts)]
        self.run_simulation = True
        self.floor_height = 600 // self.floors

        self.control_frame = tk.Frame(self.root)
        self.control_frame.pack()

        tk.Label(self.control_frame, text="From Floor: ").grid(row=0, column=0)
        self.from_floor = tk.Entry(self.control_frame)
        self.from_floor.grid(row=0, column=1)

        tk.Label(self.control_frame, text="To Floor: ").grid(row=0, column=2)
        self.to_floor = tk.Entry(self.control_frame)
        self.to_floor.grid(row=0, column=3)

        tk.Label(self.control_frame, text="Passengers: ").grid(row=0, column=4)
        self.passenger_entry = tk.Entry(self.control_frame)
        self.passenger_entry.insert(0, "1")
        self.passenger_entry.grid(row=0, column=5)

        tk.Button(self.control_frame, text="Add Request", command=self.add_user_request).grid(row=0, column=6)

        self.stats_label = tk.Label(self.root, text="")
        self.stats_label.pack()

        threading.Thread(target=self.simulation_loop, daemon=True).start()

    def add_user_request(self):
        try:
            from_f = int(self.from_floor.get())
            to_f = int(self.to_floor.get())
            passengers = int(self.passenger_entry.get())
            if from_f == to_f or not (0 <= from_f < self.floors) or not (0 <= to_f < self.floors):
                return
            direction = "UP" if to_f > from_f else "DOWN"

            valid_lifts = []
            for l in self.lifts:
                if l.direction == "IDLE":
                    valid_lifts.append(l)
                elif l.direction == direction:
                    if direction == "DOWN" and l.current_floor >= from_f:
                        valid_lifts.append(l)
                    elif direction == "UP" and l.current_floor <= from_f:
                        valid_lifts.append(l)

            if not valid_lifts:
                valid_lifts = self.lifts

            assigned_lift = min(valid_lifts, key=lambda l: (abs(l.current_floor - from_f), l.load))
            assigned_lift.add_request(from_f, direction, to_f, passengers)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            self.stats.append((timestamp, from_f, to_f, direction, assigned_lift.lift_id, passengers))
            with open(self.log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, from_f, to_f, direction, assigned_lift.lift_id, passengers])
            winsound.Beep(1000, 200)
        except ValueError:
            pass

    def simulation_loop(self):
        while self.run_simulation:
            for lift in self.lifts:
                lift.update()
            self.update_canvas()
            self.update_stats()
            time.sleep(0.1)

    def update_canvas(self):
        self.canvas.delete("all")

        up_requests = set()
        down_requests = set()
        for lift in self.lifts:
            for r in lift.pickup_requests:
                if r.direction == "UP":
                    up_requests.add(r.floor)
                else:
                    down_requests.add(r.floor)

        for f in range(self.floors):
            y = 600 - f * self.floor_height
            self.canvas.create_line(0, y, 600, y, fill="gray")
            self.canvas.create_text(20, y - 10, text=f"Floor {f}")

            if f in up_requests:
                self.canvas.create_polygon(40, y - 30, 50, y - 40, 60, y - 30, fill="green")
            if f in down_requests:
                self.canvas.create_polygon(40, y - 10, 50, y, 60, y - 10, fill="red")

        for i, lift in enumerate(self.lifts):
            y = 600 - lift.current_floor * self.floor_height
            x = 100 + i * 120
            self.canvas.create_rectangle(x, y - 40, x + 60, y, fill="lightblue")
            self.canvas.create_text(x + 30, y - 20, text=f"Lift {i}\n{lift.direction}\nLoad: {lift.load}")

    def update_stats(self):
        text = "Recent Requests:\n" + "".join([
            f"[{ts}] From F{f1} to F{f2} ({p} pax) [{d}] -> Lift #{l}\n" for (ts, f1, f2, d, l, p) in self.stats[-5:]
        ])
        self.stats_label.config(text=text)

if __name__ == "__main__":
    root = tk.Tk()
    sim = LiftSimulator(root)
    root.mainloop()
