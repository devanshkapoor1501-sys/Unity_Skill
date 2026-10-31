using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

namespace PolyForge.Game.Tests
{
    [Serializable] public class Setup {public float[] player_position;public int initial_health;}
    [Serializable] public class Step {public string action;public int ticks;public float[] direction;}
    [Serializable] public class Scenario {public string id;public int seed;public Setup setup;public Step[] steps;}
    [Serializable] public class Suite {public Scenario[] scenarios;}
    [Serializable] public class GameContract {public string input_digest;public float[] half_extents;public float wall_thickness;}
    [Serializable] public class EnemyPosition {public string id;public float[] position;}
    [Serializable] public class Sample
    {
        public int frame;public int round;public string state;public int health;public float elapsed_seconds;
        public float[] player_position;public EnemyPosition[] enemy_positions;
    }
    [Serializable] public class Trace
    {
        public string schema_version="1.0.0";public string scenario_id;public string input_digest;public string scene_id;
        public string purpose;public string mutant;public int seed;public int frames_executed;
        public float fixed_delta_seconds;public float[] arena_half_extents;public float wall_thickness;
        public float player_radius;public float[] baseline_player_position;public EnemyPosition[] baseline_enemy_positions;
        public string obstacle_id;public string obstacle_asset_id;public float[] obstacle_center_m;public float[] obstacle_size_m;
        public Sample[] samples;public ArenaEvent[] events;
    }
    public sealed class InjectedInput : IPlayerInput
    {
        public Vector2 movement;public bool restart;public bool disableRestart;
        public Vector2 Movement=>movement;
        public bool ConsumeRestart(){bool value=restart;restart=false;return value && !disableRestart;}
    }
    public class ScenarioTests
    {
        static string Arg(string key)
        {
            var args=Environment.GetCommandLineArgs();int i=Array.IndexOf(args,key);
            if(i<0 || i+1>=args.Length)throw new Exception("Missing "+key);return args[i+1];
        }
        static float[] P(Vector3 v)=>new[]{v.x,v.y,v.z};
        static Sample Observe(ArenaSession s)=>new Sample{frame=s.Frame,round=s.Round,state=s.State,health=s.player.Health.Current,elapsed_seconds=s.ElapsedSeconds,
            player_position=P(s.player.transform.position),enemy_positions=s.enemies.Select(e=>new EnemyPosition{id=e.name,position=P(e.transform.position)}).ToArray()};
        IEnumerator Run(string id,string mutant=null,bool keyboard=false,bool keyboardRestart=false)
        {
            Time.timeScale=1;Time.fixedDeltaTime=.02f;
            yield return SceneManager.LoadSceneAsync("PlayableArena",LoadSceneMode.Single);
            yield return null;
            var session=UnityEngine.Object.FindFirstObjectByType<ArenaSession>();Assert.That(session,Is.Not.Null);
            var contract=JsonUtility.FromJson<GameContract>(File.ReadAllText(Arg("-polyforgeGameInput")));
            var suite=JsonUtility.FromJson<Suite>(File.ReadAllText(Arg("-polyforgeScenarioInput")));
            var scenario=suite.scenarios.Single(x=>x.id==id);var input=new InjectedInput{disableRestart=mutant=="restart_disabled"};
            session.player.Input=input;
            // In-memory test-only defects; each scene reload restores the original production code.
            if(mutant=="input_disconnected")session.player.Input=null;
            if(mutant=="navigation_stuck")foreach(var enemy in session.enemies)enemy.speed=0;
            if(mutant=="damage_no_health")foreach(var damage in UnityEngine.Object.FindObjectsByType<ContactDamage>(FindObjectsSortMode.None))damage.amount=0;
            if(mutant=="win_reversed")session.survivalSeconds=60;
            if(scenario.setup.player_position!=null && scenario.setup.player_position.Length==3)
                session.player.ResetAt(new Vector3(scenario.setup.player_position[0],scenario.setup.player_position[1],scenario.setup.player_position[2]));
            if(scenario.setup.initial_health>0 && scenario.setup.initial_health<100)session.player.Health.Damage(100-scenario.setup.initial_health);
            if(mutant=="collision_disabled")foreach(var name in new[]{"WallNorth","WallSouth","WallEast","WallWest"})GameObject.Find(name).GetComponent<BoxCollider>().enabled=false;
            GameObject obstacle=null;Bounds obstacleBounds=default;
            if(id=="obstacle_collision")
            {
                obstacle=GameObject.Find("Obstacle_0");Assert.That(obstacle,Is.Not.Null,"Frozen brief requires an obstacle");
                var renderers=obstacle.GetComponentsInChildren<MeshRenderer>();Assert.That(renderers,Is.Not.Empty);
                obstacleBounds=renderers[0].bounds;foreach(var r in renderers.Skip(1))obstacleBounds.Encapsulate(r.bounds);
                session.player.ResetAt(new Vector3(obstacleBounds.min.x-session.player.Motor.radius-2,0,obstacleBounds.center.z));
                if(mutant=="obstacle_collision_disabled")foreach(var c in obstacle.GetComponentsInChildren<Collider>())c.enabled=false;
                Physics.SyncTransforms();
            }
            Keyboard device=null;
            var oldEditorInput=InputSystem.settings.editorInputBehaviorInPlayMode;
            var oldBackground=InputSystem.settings.backgroundBehavior;
            if(keyboard)
            {
                InputSystem.settings.editorInputBehaviorInPlayMode=InputSettings.EditorInputBehaviorInPlayMode.AllDeviceInputAlwaysGoesToGameView;
                InputSystem.settings.backgroundBehavior=InputSettings.BackgroundBehavior.IgnoreFocus;
                device=InputSystem.AddDevice<Keyboard>();session.player.Input=new KeyboardPlayerInput();
                InputSystem.QueueStateEvent(device,new KeyboardState(Key.W));InputSystem.Update();
            }
            var samples=new List<Sample>{Observe(session)};int initial=session.Frame;
            try
            {
                foreach(var step in scenario.steps)
                {
                    input.movement=step.action=="move"?new Vector2(step.direction[0],step.direction[1]):Vector2.zero;
                    input.restart=step.action=="restart";int target=session.Frame+step.ticks;
                    while(session.Frame<target)
                    {
                        yield return new WaitForFixedUpdate();
                        if(mutant=="win_reversed" && session.State=="RUNNING" && session.ElapsedSeconds<30)
                        {
                            typeof(ArenaSession).GetProperty(nameof(ArenaSession.State)).SetValue(session,"WON");
                            session.Record("won","player",session.ElapsedSeconds);
                        }
                        samples.Add(Observe(session));
                        if(samples.Count>32000)throw new Exception("Telemetry sample budget exceeded");
                    }
                }
                if(keyboardRestart)
                {
                    InputSystem.QueueStateEvent(device,new KeyboardState(Key.R));InputSystem.Update();
                    int target=session.Frame+1;
                    while(session.Frame<target){yield return new WaitForFixedUpdate();samples.Add(Observe(session));}
                }
            }
            finally
            {
                if(device!=null)InputSystem.RemoveDevice(device);
                InputSystem.settings.editorInputBehaviorInPlayMode=oldEditorInput;
                InputSystem.settings.backgroundBehavior=oldBackground;
            }
            var trace=new Trace{scenario_id=keyboardRestart?"restart_resets":id,scene_id=session.sceneId,input_digest=session.inputDigest,seed=session.seed,purpose=mutant==null?keyboard?"INPUT_ADAPTER":"NOMINAL":"MUTANT",mutant=mutant,
                frames_executed=session.Frame-initial,fixed_delta_seconds=Time.fixedDeltaTime,arena_half_extents=contract.half_extents,wall_thickness=contract.wall_thickness,player_radius=session.player.Motor.radius,
                baseline_player_position=P(session.playerSpawn),baseline_enemy_positions=session.enemies.Select(e=>new EnemyPosition{id=e.name,position=P(e.spawn)}).ToArray(),samples=samples.ToArray(),events=session.Events.ToArray()};
            if(obstacle!=null){trace.obstacle_id=obstacle.name;trace.obstacle_asset_id=obstacle.GetComponent<PrefabBinding>().semanticId;trace.obstacle_center_m=P(obstacleBounds.center);trace.obstacle_size_m=P(obstacleBounds.size);}
            string file=mutant??(keyboardRestart?"keyboard_restart":keyboard?"keyboard_input":id);var directory=Arg("-polyforgeTelemetry");Directory.CreateDirectory(directory);File.WriteAllText(Path.Combine(directory,file+".json"),JsonUtility.ToJson(trace,true));
            Assert.That(trace.frames_executed,Is.GreaterThan(0));Assert.That(samples.Count,Is.GreaterThan(1));
        }
        [UnityTest] public IEnumerator PlayerMoves()=>Run("player_moves");
        [UnityTest] public IEnumerator WallCollision()=>Run("wall_collision");
        [UnityTest] public IEnumerator ObstacleCollision()=>Run("obstacle_collision");
        [UnityTest] public IEnumerator EnemyPatrols()=>Run("enemy_patrols");
        [UnityTest] public IEnumerator ContactDealsDamage()=>Run("contact_damage");
        [UnityTest] public IEnumerator HealthFailure()=>Run("health_failure");
        [UnityTest] public IEnumerator SurvivalWins()=>Run("survival_win");
        [UnityTest] public IEnumerator RestartResets()=>Run("restart_resets");
        [UnityTest] public IEnumerator KeyboardAdapterMovesPlayer()=>Run("player_moves",keyboard:true);
        [UnityTest] public IEnumerator KeyboardAdapterRestarts()=>Run("player_moves",keyboard:true,keyboardRestart:true);
        [UnityTest] public IEnumerator CollisionDisabledMutant()=>Run("wall_collision","collision_disabled");
        [UnityTest] public IEnumerator ObstacleCollisionDisabledMutant()=>Run("obstacle_collision","obstacle_collision_disabled");
        [UnityTest] public IEnumerator RestartDisabledMutant()=>Run("restart_resets","restart_disabled");
        [UnityTest] public IEnumerator ReversedWinMutant()=>Run("survival_win","win_reversed");
        [UnityTest] public IEnumerator DamageWithoutHealthMutant()=>Run("contact_damage","damage_no_health");
        [UnityTest] public IEnumerator NavigationStuckMutant()=>Run("enemy_patrols","navigation_stuck");
        [UnityTest] public IEnumerator InputDisconnectedMutant()=>Run("player_moves","input_disconnected");
    }
}
