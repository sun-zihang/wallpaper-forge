## 改动内容

## 验证方式

- [ ] `python -m pytest -q --cov=core --cov=gui --cov-fail-under=98`
- [ ] `node --test --experimental-test-coverage --test-coverage-include='web/lib/**' --test-coverage-lines=95 web/tests/*.test.mjs`
- [ ] `python -m ruff check .` && `python -m ruff format --check .`
- [ ] `python -m mypy`
- [ ] `node scripts/check_cdn.mjs`

## 备注
