## LA-003. Fiscal/labor: живые kernels ранних базовых моделей

**Перемещение по смысловой роли**

**Статус.** Живой код; кандидат на уточнение профиля и перенос, не прямое удаление.

**Точная область:**

`src/polisyos/foundry/mechanisms/fiscal.py`

`src/polisyos/foundry/mechanisms/labor.py`

`src/polisyos/foundry/mechanisms/__init__.py`

**Что установлено и почему это legacy-кандидат.** IncomeTax/TaxSubsidy эмитируют PatchMap; LaborMarketMechanism заново выбирает занятость по threshold и фирму из равномерного распределения. Это узкие модели, а не универсальный рынок труда. Но каталог уже вызывает эти классы через runtime_mechanism_class_path: это backend зарегистрированных методов, а не забытый независимый методовый каталог.

**Что сохранить.** Patch-first ABI, active/target masks, фискальный баланс, employer IDs, firm labor counts, PRNG key progression и дешёвые контрольные модели. Существующий runtime-каталог уже ограничивает evidence/authority-scope этих методов.

**Куда перенести / с чем объединить.** Предлагаемый src/polisyos/foundry/execute/mechanisms/{fiscal,labor}.py под существующим execute/ как низкоуровневый доменный backend. Методовые adapters остаются в methods/catalog/mechanism/runtime.py. До согласования import-direction допустимо оставить текущий путь, но явно назвать профиль baseline.

**Порядок миграции.** Разделить relocation и изменение модели. Сначала эквивалентный перенос со старым method ID, затем при желании новая версия модели с иной динамикой. Обновить строковые class paths, registry descriptors и exports; не переносить численный код внутрь обёртки ради одного файла.

**Приёмочная проверка.** Регистрация, создание по spec, одинаковые patches/key при фиксированных входах, masked/inactive cases, compiler/replay и существующие fiscal/labor/gradient tests. Новый содержательный закон требует отдельной версии, а не тех же fingerprints.

**Приоритет.** Средняя цена. Выше приоритета косметического выравнивания дерева — точный статус baseline-модели.

**Граница вывода.** Простая модель не является legacy только из-за простоты. Доказательств готовой эквивалентной замены и всех production-вызовов нет; смысловая граница уже частично защищена metadata.

**Основания:** E01, E04, E05, E06.

<!-- PAGEBREAK -->
