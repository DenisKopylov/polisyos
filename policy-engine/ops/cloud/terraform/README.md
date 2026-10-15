# Terraform (`ops/cloud/terraform`)

Terraform module for a dedicated confidential node pool in AKS.

## Directory Contents

| Path                                    | Purpose                                                                                  |
| --------------------------------------- | ---------------------------------------------------------------------------------------- |
| `modules/confidential_nodepool/main.tf` | `azurerm_kubernetes_cluster_node_pool` with `KataCcIsolation` and PolicyOS labels/taints |

## Role in the System

The module prepares nodes for the confidential workload path used by `ops/cloud/helm/polisyos-cell/templates/runtimeclass-confidential.yaml`.

## Module Parameters

| Variable         | Type     | Default              | Purpose                  |
| ---------------- | -------- | -------------------- | ------------------------ |
| `cluster_id`     | `string` | -                    | AKS cluster resource ID  |
| `cell_id`        | `string` | -                    | PolicyOS cell identifier |
| `vm_size`        | `string` | `Standard_DC16as_v5` | Confidential VM size     |
| `node_count`     | `number` | `2`                  | initial/min nodes        |
| `max_node_count` | `number` | `8`                  | autoscaler maximum       |

## What the Module Configures

- `workload_runtime = "KataCcIsolation"`;
- labels: `polisyos.io/cell-id`, `polisyos.io/tier=dedicated`, `polisyos.io/tee=sev-snp`, `polisyos.io/confidential=true`;
- taint: `polisyos.io/confidential=true:NoSchedule`;
- autoscaling: `min_count=node_count`, `max_count=max_node_count`.

## Outputs

- `node_pool_id`
- `node_pool_name`

## Limitations

- the module does not include provider/backend/root wiring;
- node pool name: `cvm${substr(var.cell_id, 0, 8)}` (watch for collisions between similar `cell_id` values).

## Example

```hcl
module "cell_confidential_pool" {
  source         = "./ops/cloud/terraform/modules/confidential_nodepool"
  cluster_id     = azurerm_kubernetes_cluster.main.id
  cell_id        = "cell-00112233"
  vm_size        = "Standard_DC16as_v5"
  node_count     = 2
  max_node_count = 8
}
```
