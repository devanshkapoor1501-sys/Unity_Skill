using System;
using System.Collections.Generic;
using UnityEngine;

namespace PolyForge
{
    [Serializable] public class PlatformerSetup { public float[] position; public int health; }
    [Serializable] public class PlatformerStep { public float move; public bool jump, restart; public int ticks; }
    [Serializable] public class PlatformerScenario { public string id, schedule_digest; public PlatformerSetup setup; public PlatformerStep[] steps; }
    [Serializable] public class PlatformerSuite { public PlatformerScenario[] scenarios; }
    [Serializable] public class PlatformerSample
    {
        public int frame, health, round;
        public float elapsed_seconds;
        public float[] position, velocity;
        public bool grounded;
        public string state, checkpoint;
    }
    [Serializable] public class PlatformerTrace
    {
        public string schema_version = "1.0.0", input_digest, scene_id, scenario_id, purpose, mutant = "", schedule_digest;
        public int seed, frames_executed;
        public float fixed_delta_seconds = .02f, platform_top;
        public float[] spawn, checkpoint_position, goal_center, goal_size, hazard_center, hazard_size;
        public PlatformerSample[] samples;
        public PlatformerContact[] contacts;
    }
    public sealed class PlatformerScheduledInput : IPlatformerInput
    {
        public float move;
        public bool jump, restart;
        public Vector2 Movement => new Vector2(move, 0);
        public bool ConsumeJump() { bool value = jump; jump = false; return value; }
        public bool ConsumeRestart() { bool value = restart; restart = false; return value; }
    }
    public static class PlatformerRecording
    {
        public static float[] V(Vector3 p) => new[] { p.x, p.y, p.z };
        public static PlatformerSample Observe(PlatformerSession s) => new PlatformerSample {
            frame = s.Frame, health = s.player.Health.Current, round = s.Round,
            elapsed_seconds = s.ElapsedSeconds, position = V(s.player.transform.position),
            velocity = V(s.player.Body.linearVelocity), grounded = s.player.Grounded,
            state = s.State, checkpoint = s.Checkpoint };
        public static PlatformerTrace Trace(PlatformerSession s, PlatformerScenario scenario, List<PlatformerSample> samples,
            string purpose = "NOMINAL", string mutant = "") => new PlatformerTrace {
            input_digest = s.inputDigest, scene_id = s.sceneId, scenario_id = scenario.id,
            purpose = purpose, mutant = mutant, schedule_digest = scenario.schedule_digest, seed = s.seed,
            frames_executed = samples[samples.Count - 1].frame - samples[0].frame,
            fixed_delta_seconds = Time.fixedDeltaTime, spawn = V(s.spawn), checkpoint_position = V(s.checkpointPosition),
            goal_center = V(s.goalCenter), goal_size = V(s.goalSize), hazard_center = V(s.hazardCenter),
            hazard_size = V(s.hazardSize), samples = samples.ToArray(), contacts = s.Contacts.ToArray() };
    }
}
