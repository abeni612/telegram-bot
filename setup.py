from setuptools import setup, find_packages

setup(
    name="telegram-bot",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "python-telegram-bot==20.7",
        "python-dotenv==1.0.0", 
        "sqlalchemy==2.0.23",
        "apscheduler==3.10.4",
        "aiohttp==3.9.1"
    ],
    python_requires=">=3.10",
)