using System.Collections;
using System.Linq;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

namespace PolyForge.Animation.Tests
{
    public class MotionTests
    {
        [UnityTest] public IEnumerator IdleWalkIdleChangesActualSkinAndKeepsRootInPlace()
        {
            yield return SceneManager.LoadSceneAsync("AnimationArena");yield return null;
            var animator=Object.FindObjectsByType<Animator>(FindObjectsSortMode.None).First();
            var driver=animator.GetComponent<RobotAnimationDriver>();driver.enabled=false;
            animator.SetBool("Walking",false);yield return new WaitForSeconds(.15f);
            Assert.That(animator.GetCurrentAnimatorStateInfo(0).IsName("Idle"),Is.True);
            var bone=animator.GetComponentsInChildren<Transform>().Single(t=>t.name=="thigh_l");
            var skin=animator.GetComponentsInChildren<SkinnedMeshRenderer>().Single(s=>s.name.EndsWith(":module:thigh_l"));
            var mesh=new Mesh();skin.BakeMesh(mesh);var first=mesh.vertices[0];var pose=bone.localRotation;var origin=animator.transform.localPosition;
            animator.SetBool("Walking",true);yield return new WaitForSeconds(.25f);
            Assert.That(animator.GetCurrentAnimatorStateInfo(0).IsName("Walk"),Is.True);
            Assert.That(Quaternion.Angle(pose,bone.localRotation),Is.GreaterThan(5));skin.BakeMesh(mesh);
            Assert.That(Vector3.Distance(first,mesh.vertices[0]),Is.GreaterThan(.01f));
            Assert.That(Vector3.Distance(origin,animator.transform.localPosition),Is.LessThan(.001f));
            animator.SetBool("Walking",false);yield return new WaitForSeconds(.15f);
            Assert.That(animator.GetCurrentAnimatorStateInfo(0).IsName("Idle"),Is.True);Object.Destroy(mesh);
        }
        [UnityTest] public IEnumerator PatrolDrivesWalkAndTerminalStateDrivesIdle()
        {
            yield return SceneManager.LoadSceneAsync("AnimationArena");yield return new WaitForSeconds(.3f);
            var animator=Object.FindObjectsByType<Animator>(FindObjectsSortMode.None).First();
            Assert.That(animator.GetCurrentAnimatorStateInfo(0).IsName("Walk"),Is.True);
            var session=Object.FindFirstObjectByType<ArenaSession>();session.player.Health.Damage(100);
            yield return new WaitForSeconds(.2f);Assert.That(animator.GetCurrentAnimatorStateInfo(0).IsName("Idle"),Is.True);
        }
    }
}
