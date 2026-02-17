# Terraform (`ops/terraform`)

Terraform-модуль для выделенного confidential node pool в AKS.

## Структура

| Путь | Назначение |
|---|---|
| `modules/confidential_nodepool/main.tf` | модуль `azurerm_kubernetes_cluster_node_pool` с confidential runtime настройками |

## Что конфигурирует модуль

- `workload_runtime = "KataCcIsolation"`;
- labels для PolicyOS scheduling:
  - `polisyos.io/cell-id=<cell_id>`;
  - `polisyos.io/tier=dedicated`;
  - `polisyos.io/tee=sev-snp`;
  - `polisyos.io/confidential=true`;
- taint: `polisyos.io/confidential=true:NoSchedule`;
- autoscaling (`min_count=node_count`, `max_count=max_node_count`).

## Входные переменные

| Переменная | Тип | По умолчанию | Назначение |
|---|---|---|---|
| `cluster_id` | `string` | - | resource ID AKS кластера |
| `cell_id` | `string` | - | идентификатор PolicyOS cell |
| `vm_size` | `string` | `Standard_DC16as_v5` | размер confidential VM |
| `node_count` | `number` | `2` | начальное и минимальное число нод |
| `max_node_count` | `number` | `8` | верхняя граница autoscaler |

## Outputs

- `node_pool_id`
- `node_pool_name`

## Пример использования

```hcl
module "cell_confidential_pool" {
  source         = "./ops/terraform/modules/confidential_nodepool"
  cluster_id     = azurerm_kubernetes_cluster.main.id
  cell_id        = "cell-00112233"
  vm_size        = "Standard_DC16as_v5"
  node_count     = 2
  max_node_count = 8
}
```

## Связь с Helm

`ops/helm/polisyos-cell/templates/runtimeclass-confidential.yaml` ожидает ноды с label `polisyos.io/tee=sev-snp` и taint `polisyos.io/confidential=true:NoSchedule`, которые как раз создает этот модуль.

## Ограничения модуля

- В модуле нет provider/backend конфигурации (они задаются в корневом Terraform проекте).
- Naming node pool: `cvm${substr(var.cell_id, 0, 8)}`; следите за коллизиями при схожих `cell_id`.
