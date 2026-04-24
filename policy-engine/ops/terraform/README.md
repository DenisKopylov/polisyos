# Terraform (`ops/terraform`)

Terraform модуль для dedicated confidential node pool в AKS.

## Что есть в директории

| Путь                                    | Назначение                                                                             |
| --------------------------------------- | -------------------------------------------------------------------------------------- |
| `modules/confidential_nodepool/main.tf` | `azurerm_kubernetes_cluster_node_pool` с `KataCcIsolation`, labels/taints для PolicyOS |

## Роль в системе

Модуль подготавливает ноды под confidential workload path, который использует `ops/helm/polisyos-cell/templates/runtimeclass-confidential.yaml`.

## Параметры модуля

| Переменная       | Тип      | По умолчанию         | Назначение                  |
| ---------------- | -------- | -------------------- | --------------------------- |
| `cluster_id`     | `string` | -                    | resource ID AKS кластера    |
| `cell_id`        | `string` | -                    | идентификатор PolicyOS cell |
| `vm_size`        | `string` | `Standard_DC16as_v5` | размер Confidential VM      |
| `node_count`     | `number` | `2`                  | initial/min nodes           |
| `max_node_count` | `number` | `8`                  | autoscaler maximum          |

## Что настраивается

- `workload_runtime = "KataCcIsolation"`;
- labels: `polisyos.io/cell-id`, `polisyos.io/tier=dedicated`, `polisyos.io/tee=sev-snp`, `polisyos.io/confidential=true`;
- taint: `polisyos.io/confidential=true:NoSchedule`;
- autoscaling: `min_count=node_count`, `max_count=max_node_count`.

## Outputs

- `node_pool_id`
- `node_pool_name`

## Ограничения

- модуль не включает provider/backend/root wiring;
- node pool name: `cvm${substr(var.cell_id, 0, 8)}` (следить за коллизиями при близких `cell_id`).

## Пример

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
