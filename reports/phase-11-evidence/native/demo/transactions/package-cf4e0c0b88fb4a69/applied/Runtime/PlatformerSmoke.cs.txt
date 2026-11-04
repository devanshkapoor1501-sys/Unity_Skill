using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace PolyForge
{
    [Serializable] public class PlatformerSmokeReport { public string input_digest, scene; public int frames; }
    public sealed class PlatformerSmoke : MonoBehaviour
    {
        static bool started;
        static string Arg(string key)
        {
            var args = Environment.GetCommandLineArgs(); int index = Array.IndexOf(args, key);
            if (index < 0 || index + 1 >= args.Length) throw new InvalidOperationException("Missing " + key);
            return args[index + 1];
        }
        void Start()
        {
            if (started || Array.IndexOf(Environment.GetCommandLineArgs(), "-polyforgePlatformerSmoke") < 0) return;
            started = true; DontDestroyOnLoad(gameObject); StartCoroutine(Run());
        }
        IEnumerator Run()
        {
            var suite = JsonUtility.FromJson<PlatformerSuite>(File.ReadAllText(Arg("-polyforgeScenarioInput")));
            string directory = Arg("-polyforgeTelemetry"), digest = null; int frames = 0;
            Directory.CreateDirectory(directory); Time.timeScale = 1; Time.fixedDeltaTime = .02f;
            foreach (var scenario in suite.scenarios)
            {
                yield return SceneManager.LoadSceneAsync("SpritePlatformer", LoadSceneMode.Single);
                yield return null;
                var session = UnityEngine.Object.FindFirstObjectByType<PlatformerSession>();
                // The recorder persists on its own GameObject, never the scene session.
                if (session == null) throw new InvalidOperationException("Missing platformer session");
                var input = new PlatformerScheduledInput(); session.player.Input = input;
                yield return new WaitForFixedUpdate(); yield return new WaitForFixedUpdate();
                session.player.ResetAt(new Vector3(scenario.setup.position[0], scenario.setup.position[1], scenario.setup.position[2]));
                if (scenario.setup.health > 0) session.player.Health.Damage(3 - scenario.setup.health);
                var samples = new List<PlatformerSample> { PlatformerRecording.Observe(session) };
                foreach (var step in scenario.steps)
                {
                    input.move = step.move; input.jump = step.jump; input.restart = step.restart;
                    int target = session.Frame + step.ticks;
                    while (session.Frame < target) { yield return new WaitForFixedUpdate(); samples.Add(PlatformerRecording.Observe(session)); }
                }
                var trace = PlatformerRecording.Trace(session, scenario, samples); frames += trace.frames_executed; digest = session.inputDigest;
                File.WriteAllText(Path.Combine(directory, scenario.id + ".json"), JsonUtility.ToJson(trace, true));
            }
            File.WriteAllText(Arg("-polyforgePlayerEvidence"), JsonUtility.ToJson(new PlatformerSmokeReport {
                input_digest = digest, scene = "SpritePlatformer", frames = frames }, true));
            Application.Quit(0);
        }
    }
}
