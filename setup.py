from setuptools import setup

setup(
    name='hsharp',
    version='0.4.0',
    description='H# language (v0.4) interpreter and tooling',
    py_modules=[
        'hsharp', 'lexer', 'parser', 'interpreter', 'compiler', 'bytecode', 'tokens', 'ast'
    ],
    entry_points={
        'console_scripts': [
            'hsharp=hsharp:main',
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
