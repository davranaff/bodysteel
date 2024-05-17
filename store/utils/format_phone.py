import re

def format_phone_number(phone_number):
    """
    Преобразует номер телефона из формата +998 (12) 345-12-23 в +998123451223.
    """
    # Удаляем все символы, кроме цифр
    cleaned_number = re.sub(r'\D', '', phone_number)
    
    # Проверяем, начинается ли номер с +998
    if cleaned_number.startswith('998'):
        cleaned_number = '+' + cleaned_number
    
    return cleaned_number