using NUnit.Framework;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using System;
using System.Linq;

namespace PolyForge.Game.Editor.Tests
{
    public class GameTests
    {
        [Test] public void PlayableSceneHasLiveRuntimeBindingsAndFourBoundaries()
        {
            var scene=EditorSceneManager.OpenScene(GameBuilder.ScenePath,OpenSceneMode.Single);
            var session=UnityEngine.Object.FindFirstObjectByType<ArenaSession>();
            Assert.That(session,Is.Not.Null);
            var job=GameBuilder.Read();
            Assert.That(session.inputDigest,Is.EqualTo(job.input_digest),"Stale scene input identity");
            Assert.That(session.seed,Is.EqualTo(job.seed),"Stale scene seed");
            Assert.That(session.sceneId,Is.EqualTo(job.scene_id));
            Assert.That(session.player.name,Is.EqualTo(job.player.id));
            Assert.That(Vector3.Distance(session.playerSpawn,new Vector3(job.player.spawn_xyz[0],job.player.spawn_xyz[1],job.player.spawn_xyz[2])),Is.LessThan(.001f));
            Assert.That(session.survivalSeconds,Is.EqualTo(job.survival_seconds));
            Assert.That(session.enemies.Select(e=>e.name),Is.EquivalentTo(job.enemies.Select(e=>e.id)));
            foreach(var expected in job.enemies)
            {
                var actual=session.enemies.Single(e=>e.name==expected.id);
                Assert.That(Vector3.Distance(actual.spawn,new Vector3(expected.spawn_xyz[0],expected.spawn_xyz[1],expected.spawn_xyz[2])),Is.LessThan(.001f));
            }
            Assert.That(session.player,Is.Not.Null);
            Assert.That(session.player.GetComponent<CharacterController>().enabled,Is.True);
            Assert.That(session.player.GetComponent<Health>(),Is.Not.Null);
            Assert.That(session.enemies.Length,Is.GreaterThan(0));
            foreach(var enemy in session.enemies)
            {
                Assert.That(enemy.session,Is.EqualTo(session));
                Assert.That(enemy.GetComponent<Rigidbody>().isKinematic,Is.True);
                Assert.That(enemy.GetComponent<ContactDamage>(),Is.Not.Null);
            }
            foreach(var name in new[]{"WallNorth","WallSouth","WallEast","WallWest"})
                Assert.That(GameObject.Find(name).GetComponent<BoxCollider>().enabled,Is.True);
            Assert.That(UnityEngine.Object.FindFirstObjectByType<ArenaHud>().session,Is.EqualTo(session));
            Assert.That(Camera.main,Is.Not.Null);
            Assert.That(scene.IsValid(),Is.True);
        }
    }
}
