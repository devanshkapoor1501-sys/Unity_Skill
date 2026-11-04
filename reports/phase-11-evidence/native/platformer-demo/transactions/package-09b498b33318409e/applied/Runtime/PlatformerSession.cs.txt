using System;
using System.Collections.Generic;
using UnityEngine;

namespace PolyForge
{
    [Serializable] public class PlatformerContact { public int frame; public string kind; public float[] position; }
    [DefaultExecutionOrder(-100)]
    public sealed class PlatformerSession : MonoBehaviour
    {
        public string inputDigest, sceneId;
        public int seed;
        public PlatformerPlayer player;
        public Vector3 spawn = new Vector3(-8, 0, 0), checkpointPosition = new Vector3(-3, 0, 0);
        public Vector3 goalCenter = new Vector3(8, 1, 0), goalSize = new Vector3(1, 2, 1);
        public Vector3 hazardCenter = new Vector3(.5f, .3f, 0), hazardSize = new Vector3(.8f, .6f, 1);
        public string State { get; private set; } = "RUNNING";
        public string Checkpoint { get; private set; } = "spawn";
        public int Round { get; private set; } = 1;
        public int Frame { get; private set; }
        public float ElapsedSeconds { get; private set; }
        public readonly List<PlatformerContact> Contacts = new List<PlatformerContact>();
        void FixedUpdate() { Frame++; if (State == "RUNNING") ElapsedSeconds += Time.fixedDeltaTime; }
        public void Touch(PlatformerTrigger.Kind kind, int damage)
        {
            if (State != "RUNNING") return;
            if (Contacts.Count < 256) Contacts.Add(new PlatformerContact { frame = Frame, kind = kind.ToString(), position = PlatformerRecording.V(player.transform.position) });
            if (kind == PlatformerTrigger.Kind.Checkpoint) Checkpoint = "checkpoint";
            else if (kind == PlatformerTrigger.Kind.Goal) State = "WON";
            else
            {
                player.Health.Damage(damage);
                if (player.Health.Current <= 0) State = "FAILED";
                else player.ResetAt(Checkpoint == "checkpoint" ? checkpointPosition : spawn);
            }
        }
        public void Restart()
        {
            Round++; State = "RUNNING"; Checkpoint = "spawn"; ElapsedSeconds = 0;
            player.Health.ResetHealth(); player.ResetAt(spawn);
        }
    }
}
