from database import SessionLocal, Dish

db = SessionLocal()
db.query(Dish).delete()
dishes = [
    ("Суп куриный", "Лёгкий куриный бульон с лапшой", 200, 300, "супы", "normal,diabetic"),
    ("Гречка с котлетой", "Гречневая каша, паровая куриная котлета", 450, 350, "горячее", "normal,diabetic"),
    ("Салат овощной", "Свежие огурцы, помидоры, масло", 120, 150, "салаты", "normal,diabetic,allergy"),
    ("Молочная каша", "Рисовая каша на молоке с сахаром", 350, 250, "завтрак", "normal"),
    ("Фруктовое пюре", "Яблочно-грушевое пюре без сахара", 90, 100, "десерт", "diabetic,allergy"),
    ("Омлет с сыром", "Паровой омлет с твёрдым сыром", 280, 200, "завтрак", "normal"),
    ("Рыба на пару", "Филе минтая, овощной гарнир", 320, 300, "горячее", "normal,diabetic")
]
for name, desc, cal, w, cat, diets in dishes:
    db.add(Dish(name=name, description=desc, calories=cal, weight=w, category=cat, allowed_diets=diets))
db.commit()
db.close()
print("Блюда перезаписаны в UTF-8")