using UnityEngine;

namespace PolyForge
{
    // A semantic binding, not an implementation of future gameplay controllers.
    public sealed class PrefabBinding : MonoBehaviour
    {
        public string semanticId;
        public GameObject sourceModel;
    }
}
