using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;

public class ItemClickHandler : MonoBehaviour, IPointerClickHandler
{
    public InventoryItemBase Item { get; set; }

    public void OnPointerClick(PointerEventData eventData)
    {
        if (eventData.button == PointerEventData.InputButton.Left)
        {
            Inventory.Instance.UseItem(Item);
        }
        else if (eventData.button == PointerEventData.InputButton.Right)
        {
            Inventory.Instance.RemoveItem(Item);
        }
    }
}
