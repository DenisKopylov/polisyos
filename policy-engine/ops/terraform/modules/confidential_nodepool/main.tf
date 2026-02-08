variable "cluster_id" {
  type        = string
  description = "AKS cluster resource ID"
}

variable "cell_id" {
  type        = string
  description = "PolicyOS cell identifier"
}

variable "vm_size" {
  type        = string
  default     = "Standard_DC16as_v5"
  description = "Azure Confidential VM size"
}

variable "node_count" {
  type        = number
  default     = 2
  description = "Initial number of confidential nodes"
}

variable "max_node_count" {
  type        = number
  default     = 8
  description = "Autoscaler maximum"
}

resource "azurerm_kubernetes_cluster_node_pool" "confidential" {
  name                  = "cvm${substr(var.cell_id, 0, 8)}"
  kubernetes_cluster_id = var.cluster_id
  vm_size               = var.vm_size

  node_count          = var.node_count
  min_count           = var.node_count
  max_count           = var.max_node_count
  enable_auto_scaling = true

  os_type = "Linux"
  os_sku  = "AzureLinux"

  workload_runtime = "KataCcIsolation"

  node_labels = {
    "polisyos.io/cell-id"              = var.cell_id
    "polisyos.io/tier"                 = "dedicated"
    "polisyos.io/tee"                  = "sev-snp"
    "polisyos.io/confidential"         = "true"
    "node.kubernetes.io/instance-type" = var.vm_size
  }

  node_taints = [
    "polisyos.io/confidential=true:NoSchedule",
  ]

  tags = {
    Environment = "production"
    CellID      = var.cell_id
    Security    = "confidential-computing"
    Compliance  = "fedramp-high"
  }
}

output "node_pool_id" {
  value = azurerm_kubernetes_cluster_node_pool.confidential.id
}

output "node_pool_name" {
  value = azurerm_kubernetes_cluster_node_pool.confidential.name
}
