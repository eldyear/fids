# flights/services_to_techcard.py

def generate_tech_card_from_services(flight):
    """
    Формирует текст технической карты на основе услуг, добавленных к рейсу.
    """
    services = flight.services.all().order_by('service_type__name', 'id')
    if not services:
        return "" # Если услуг нет, возвращаем пустую строку

    tech_card_lines = []
    for i, service in enumerate(services, 1):
        line = f"[{i}] {service.service_type.name} - {service.quantity} {service.unit_of_measure}"
        if service.description:
            line += f" - {service.description}"
        tech_card_lines.append(line)
    
    return "\n".join(tech_card_lines)