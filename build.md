⏺ # 1. Install build tools (if not already)
  pip install build twine

  # 2. Build the package
  python -m build
  # Creates dist/aicommitter-1.0.9.tar.gz and dist/aicommitter-1.0.9-py3-none-any.whl

  # 3. Upload to PyPI
  twine upload dist/*
  # Prompts for PyPI username (__token__) and password (your API token)

  If you want to test first, upload to TestPyPI:
  twine upload --repository testpypi dist/*
  pip install --index-url https://test.pypi.org/simple/ aicommitter

  Before building, clean old builds to avoid uploading stale artifacts:
  rm -rf dist/ build/ src/*.egg-info

  One thing — you'll need a PyPI API token. If you don't have one, create it at https://pypi.org/manage/account/token/. You can also store it in ~/.pypirc so
  you don't get prompted each time:

  [pypi]
  username = __token__
  password = pypi-xxxxxxxxxxxxxxxx
