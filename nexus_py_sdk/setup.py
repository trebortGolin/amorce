from setuptools import setup, find_packages

setup(
    name="nexus-py-sdk",
    version="0.1.0",
    description="Official Python SDK for the Nexus Agent Transaction Protocol (NATP)",
    author="Athena Architecture",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "cryptography>=43.0.0",
        "pydantic>=2.0.0",
        "requests>=2.31.0",
        "google-cloud-secret-manager>=2.16.0",
    ],
)