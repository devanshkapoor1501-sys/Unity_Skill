using System.Collections;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;

namespace PolyForge.Game.Tests
{
    public class RuntimeTests
    {
        [Test] public void HealthClampsDamageAndResets()
        {
            var go = new GameObject("health fixture");
            try
            {
                var health=go.AddComponent<Health>(); health.Configure(100,100);
                health.Damage(25); Assert.That(health.Current,Is.EqualTo(75));
                health.Damage(1000); Assert.That(health.Current,Is.Zero);
                health.ResetHealth(); Assert.That(health.Current,Is.EqualTo(100));
            }
            finally { Object.DestroyImmediate(go); }
        }
    }
}
