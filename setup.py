from setuptools import setup, find_packages
from pip.req import parse_requirements

install_reqs = parse_requirements("requirements.txt", session=False)
reqs = [str(ir.req) for ir in install_reqs]


setup(
    name="wserver",
    version="0.0.1",
    author="TianQinS",
    author_email="",
    description="",
    long_description="",
    url="https://github.com/TianQinS/wserver",
    license="MIT",
    keywords=["websocket", "socket"],
    packages=find_packages(exclude=["js"]),
    package_data={},
    install_requires=reqs,
    classifiers=[
        "Programming Language :: Python :: 3.7",
    ],
)