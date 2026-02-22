from aiogram.fsm.state import State, StatesGroup


class LangState(StatesGroup):
    choosing = State()

class RoleState(StatesGroup):
    choosing = State()

class ClientRegState(StatesGroup):
    name = State()
    phone = State()

class DriverRegState(StatesGroup):
    name = State()
    age = State()
    phone = State()
    car_number = State()
    car_model = State()
    car_color = State()

class OrderState(StatesGroup):
    from_location = State()
    to_location = State()
    people_count = State()

# ── PROFILE EDIT ──────────────────────────────────────────────────────────────

class ClientEditState(StatesGroup):
    choosing_field = State()
    editing_name = State()
    editing_phone = State()

class DriverEditState(StatesGroup):
    choosing_field = State()
    editing_name = State()
    editing_phone = State()
    editing_car_number = State()
    editing_car_model = State()
    editing_car_color = State()
