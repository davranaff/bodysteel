# store/management/commands/generate_fake_data.py

import random
from django.core.management.base import BaseCommand
from faker import Faker
from store.models import Category, Product, Blog, Brand, Filial, SetOfProduct, ProductImage, Review, Basket, Favorite, Order
from users.models import User

fake = Faker()

class Command(BaseCommand):
    help = 'Generate fake data for the store app'

    def handle(self, *args, **kwargs):
        self.generate_categories()
        self.generate_brands()
        self.generate_set_of_products()
        self.generate_products()
        self.generate_blogs()
        self.generate_filials()
        self.generate_users()
        self.generate_product_images()
        self.generate_reviews()
        self.generate_baskets()
        self.generate_favorites()
        self.generate_orders()

    def generate_categories(self):
        for _ in range(10):
            Category.objects.create(
                name_uz=fake.word(),
                name_ru=fake.word(),
                photo=fake.image_url(),
                slug=fake.slug(),
                description=fake.text(),
                sort=random.randint(1, 100)
            )

    def generate_brands(self):
        for _ in range(10):
            Brand.objects.create(
                name=fake.company(),
                photo=fake.image_url()
            )

    def generate_set_of_products(self):
        for _ in range(10):
            SetOfProduct.objects.create(
                name_uz=fake.word(),
                name_ru=fake.word(),
                slug=fake.slug(),
                photo=fake.image_url()
            )

    def generate_products(self):
        categories = list(Category.objects.all())
        brands = list(Brand.objects.all())
        sets_of_products = list(SetOfProduct.objects.all())
        for _ in range(50):
            price = random.randint(10000, 100000)
            discounted_price = random.randint(0, price)  # Ensure discounted_price is not higher than price
            product = Product.objects.create(
                name_uz=fake.word(),
                name_ru=fake.word(),
                description_uz=fake.text(),
                description_ru=fake.text(),
                price=price,
                is_new=random.choice([True, False]),
                quantity=random.randint(1, 100),
                discounted_price=discounted_price,
                slug=fake.slug(),
                country_uz=fake.country(),
                country_ru=fake.country(),
                composition_uz=fake.text(),
                composition_ru=fake.text(),
                view_count=random.randint(0, 1000),
                brand=random.choice(brands) if brands else None,
                set_of_products=random.choice(sets_of_products) if sets_of_products else None
            )
            product.category.set(random.sample(categories, k=3))

    def generate_blogs(self):
        for _ in range(10):
            Blog.objects.create(
                name_uz=fake.sentence(),
                name_ru=fake.sentence(),
                photo=fake.image_url(),
                description_uz=fake.text(),
                description_ru=fake.text(),
                slug=fake.slug()
            )

    def generate_filials(self):
        for _ in range(10):
            Filial.objects.create(
                name_uz=fake.company(),
                name_ru=fake.company(),
                address_uz=fake.address(),
                address_ru=fake.address(),
                work_time_start=fake.time(),
                work_time_end=fake.time(),
                day_off=fake.day_of_week(),
                phone=fake.phone_number(),
                address_url=fake.url(),
                address_location=fake.url(),
                photo=fake.image_url()
            )

    def generate_users(self):
        for _ in range(10):
            User.objects.create_user(
                username=fake.user_name(),
                email=fake.email(),
                password='password123'
            )

    def generate_product_images(self):
        products = list(Product.objects.all())
        for _ in range(100):
            ProductImage.objects.create(
                product=random.choice(products),
                photo=fake.image_url()
            )

    def generate_reviews(self):
        users = list(User.objects.all())
        products = list(Product.objects.all())
        for _ in range(100):
            Review.objects.create(
                full_name=fake.name(),
                rating=random.randint(1, 5),
                comment=fake.text(),
                user=random.choice(users) if users else None,
                product=random.choice(products) if products else None
            )

    def generate_baskets(self):
        users = list(User.objects.all())
        products = list(Product.objects.all())
        for _ in range(50):
            Basket.objects.create(
                price=random.randint(1000, 100000),
                quantity=random.randint(1, 10),
                user=random.choice(users) if users else None,
                product=random.choice(products) if products else None,
                order=None
            )

    def generate_favorites(self):
        users = list(User.objects.all())
        products = list(Product.objects.all())
        for _ in range(50):
            Favorite.objects.create(
                user=random.choice(users) if users else None,
                product=random.choice(products) if products else None
            )

    def generate_orders(self):
        users = list(User.objects.all())
        for _ in range(50):
            Order.objects.create(
                total_price=random.randint(10000, 100000),
                type=random.choice(['dcb', 'dtu', 'pickup']),
                full_name=fake.name(),
                phone=fake.phone_number(),
                fix_check=None,
                address=fake.address(),
                status=random.choice(['purchased', 'moderation']),
                order_code=fake.uuid4()
            )
