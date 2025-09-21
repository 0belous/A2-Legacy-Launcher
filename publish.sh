rmdir /s /q dist
python -m build
twine upload dist/*