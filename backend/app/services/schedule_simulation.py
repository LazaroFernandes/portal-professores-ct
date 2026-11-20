"""A proposed weekly schedule, independent from the official teacher schedule."""
KEY = 'teacher_schedule_simulation_v1'


def proposed_teachers(teachers, overrides):
    changes = {item['teacher_id']: item['shifts'] for item in overrides}
    return [{**teacher, 'shifts': changes.get(teacher.get('id'), teacher['shifts'])} for teacher in teachers]
