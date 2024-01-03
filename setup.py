from setuptools import setup, find_packages

setup(
    name='Flask-SQL-Pro',
    version='4.7',
    description='Based on Flask-SQLAlchemy, extract SQL statements, use Jinja2 syntax to achieve dynamic SQL, support contextual transactions, support paging',
    long_description=open('README.rst').read(),
    author='miaokela',
    author_email='2972799448@qq.com',
    maintainer='miaokela',
    maintainer_email='2972799448@qq.com',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'flask',
        'flask_sqlalchemy',
        'pyyaml',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy'
    ],
)
