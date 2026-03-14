from setuptools import setup, find_packages

setup(
    name="pyoz",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "httpx>=0.27.0",
    ],
    extras_require={
        "treesitter": ["tree-sitter-languages>=1.10.0"],
    },
    entry_points={
        "console_scripts": [
            "pyoz=pyoz.cli:main",
        ],
    },
    python_requires=">=3.11",
)
