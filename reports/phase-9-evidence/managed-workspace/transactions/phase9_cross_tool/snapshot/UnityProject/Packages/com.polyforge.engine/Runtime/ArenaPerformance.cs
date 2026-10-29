using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace PolyForge
{
    [Serializable] public class DevelopmentMetrics
    {
        public string schema_version="1.0.0";public string scope="DEVELOPMENT_TELEMETRY";
        public string profile_status="NOT_RUN";public bool qualification=false;public string smoke_status;
        public string input_digest;public string unity_version;public string scene;public int frames;
        public int width;public int height;public string quality;public string renderer;
        public string processor;public int processor_count;public int system_memory_mb;
        public long peak_rss_bytes;public float load_seconds;public float[] frame_times_ms;
    }
    public sealed class ArenaPerformance : MonoBehaviour
    {
        public ArenaSession session;
        readonly List<float> frameTimes=new List<float>();
        float loadSeconds;bool finished;
        static string Arg(string key)
        {
            var args=Environment.GetCommandLineArgs();int i=Array.IndexOf(args,key);
            return i>=0 && i+1<args.Length?args[i+1]:null;
        }
        void Start(){loadSeconds=Time.realtimeSinceStartup;}
        void Update()
        {
            if(frameTimes.Count<18000)frameTimes.Add(Time.unscaledDeltaTime*1000);
            if(!finished && Array.IndexOf(Environment.GetCommandLineArgs(),"-polyforgeSmoke")>=0 && session.Frame>=150)
            {
                bool valid=session.State=="RUNNING" && session.player.Health.Current>0 && session.enemies.Length>0;
                foreach(var enemy in session.enemies)valid&=Vector3.Distance(enemy.transform.position,enemy.spawn)>.1f;
                Write(valid?"PASS":"FAIL");finished=true;Application.Quit(valid?0:7);
            }
        }
        void OnApplicationQuit(){if(!finished)Write("NOT_RUN");}
        void Write(string smoke)
        {
            string path=Arg("-polyforgePlayerEvidence");if(string.IsNullOrEmpty(path))return;
            var parent=Path.GetFullPath(Path.GetDirectoryName(Application.dataPath))+Path.DirectorySeparatorChar;
            path=Path.GetFullPath(path);
            if(!path.StartsWith(parent,StringComparison.OrdinalIgnoreCase))throw new InvalidOperationException("Player evidence must stay below the player directory");
            long rss=0;try{rss=System.Diagnostics.Process.GetCurrentProcess().PeakWorkingSet64;}catch(InvalidOperationException){}
            var metrics=new DevelopmentMetrics{smoke_status=smoke,input_digest=session.inputDigest,unity_version=Application.unityVersion,
                scene=SceneManager.GetActiveScene().name,frames=session.Frame,width=Screen.width,height=Screen.height,quality=QualitySettings.names[QualitySettings.GetQualityLevel()],
                renderer=SystemInfo.graphicsDeviceName,processor=SystemInfo.processorType,processor_count=SystemInfo.processorCount,system_memory_mb=SystemInfo.systemMemorySize,
                peak_rss_bytes=rss,load_seconds=loadSeconds,frame_times_ms=frameTimes.ToArray()};
            Directory.CreateDirectory(Path.GetDirectoryName(path));File.WriteAllText(path,JsonUtility.ToJson(metrics,true));
            Debug.Log("POLYFORGE_PLAYER_SMOKE "+smoke);
        }
    }
}
