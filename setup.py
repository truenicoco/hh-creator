from setuptools import setup


setup(
    name="hh_creator",
    version="0.0.1",
    install_requires=[
        "poker",
        "deuces@git+https://github.com/truenicoco/deuces.git",
        "PyQt5",
    ],
    packages=["hh_creator"],
    package_data={"hh_creator": ["resource/**", "resource/**/*", "resource/**/**/*"]},
)
