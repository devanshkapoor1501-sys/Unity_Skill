using System;
using UnityEngine;

namespace PolyForge
{
    public sealed class Health : MonoBehaviour
    {
        [SerializeField] int maximum=100;
        [SerializeField] int starting=100;
        public int Current {get; private set;}
        public int Maximum => maximum;
        public event Action<int> Changed;
        void Awake() => ResetHealth();
        public void Configure(int max, int initial)
        {
            if(max<=0 || initial<=0 || initial>max) throw new ArgumentOutOfRangeException(nameof(initial));
            maximum=max;starting=initial;ResetHealth();
        }
        public void Damage(int amount)
        {
            if(amount<0) throw new ArgumentOutOfRangeException(nameof(amount));
            Current=Mathf.Max(0,Current-amount);Changed?.Invoke(Current);
        }
        public void ResetHealth() {Current=starting;Changed?.Invoke(Current);}
    }
}
