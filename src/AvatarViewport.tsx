import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

type AvatarViewportProps = {
  variant: 'preview' | 'companion';
};

const modelUrl = `${import.meta.env.BASE_URL}models/ecy-avatar.glb`;

function disposeMaterial(material: THREE.Material) {
  const values = Object.values(material) as unknown[];
  for (const value of values) {
    if (value instanceof THREE.Texture) value.dispose();
  }
  material.dispose();
}

export function AvatarViewport({ variant }: AvatarViewportProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(34, 1, 0.01, 1000);
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'high-performance' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, variant === 'companion' ? 1.15 : 1.5));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.08;
    renderer.setClearColor(0x000000, 0);
    renderer.domElement.setAttribute('aria-hidden', 'true');
    host.appendChild(renderer.domElement);

    scene.add(new THREE.HemisphereLight(0xe8ffff, 0x10131c, 2.4));
    const keyLight = new THREE.DirectionalLight(0xffffff, 3.1);
    keyLight.position.set(3, 4, 5);
    scene.add(keyLight);
    const fillLight = new THREE.DirectionalLight(0x78d9ff, 1.8);
    fillLight.position.set(-4, 2, 2);
    scene.add(fillLight);
    const rimLight = new THREE.DirectionalLight(0x8affda, 2.2);
    rimLight.position.set(1, 3, -4);
    scene.add(rimLight);

    const controls = variant === 'preview' ? new OrbitControls(camera, renderer.domElement) : null;
    if (controls) {
      controls.enableDamping = true;
      controls.enablePan = false;
      controls.rotateSpeed = 0.55;
      controls.zoomSpeed = 0.65;
      controls.target.set(0, 0, 0);
    }

    let avatar: THREE.Group | null = null;
    let avatarSize = new THREE.Vector3(1, 1, 1);
    let animationFrame = 0;
    let disposed = false;
    const timer = new THREE.Timer();
    timer.connect(document);

    const fitCamera = () => {
      const width = Math.max(host.clientWidth, 1);
      const height = Math.max(host.clientHeight, 1);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      if (!avatar) return;

      const verticalFov = THREE.MathUtils.degToRad(camera.fov);
      const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * camera.aspect);
      const fitHeight = avatarSize.y / (2 * Math.tan(verticalFov / 2));
      const fitWidth = avatarSize.x / (2 * Math.tan(horizontalFov / 2));
      const distance = Math.max(fitHeight, fitWidth, avatarSize.z) * (variant === 'companion' ? 1.4 : 1.68);
      const focusY = avatarSize.y * (variant === 'companion' ? 0.32 : 0.2);
      camera.near = Math.max(distance / 100, 0.01);
      camera.far = Math.max(distance * 40, 100);
      camera.position.set(0, focusY, distance);
      camera.lookAt(0, focusY, 0);
      camera.updateProjectionMatrix();
      if (controls) {
        controls.target.set(0, focusY, 0);
        controls.minDistance = distance * 0.72;
        controls.maxDistance = distance * 1.9;
        controls.update();
      }
    };

    const resizeObserver = new ResizeObserver(fitCamera);
    resizeObserver.observe(host);

    new GLTFLoader().load(
      modelUrl,
      (gltf) => {
        if (disposed) return;
        avatar = gltf.scene;
        const removable: THREE.Object3D[] = [];
        avatar.traverse((object) => {
          if (object instanceof THREE.Camera || object instanceof THREE.Light || object.name === '_gltfNode_243') removable.push(object);
          if (object instanceof THREE.Mesh) {
            object.castShadow = false;
            object.receiveShadow = false;
          }
        });
        removable.forEach((object) => object.parent?.remove(object));

        const bounds = new THREE.Box3().setFromObject(avatar);
        const center = bounds.getCenter(new THREE.Vector3());
        avatarSize = bounds.getSize(new THREE.Vector3());
        avatar.position.sub(center);
        scene.add(avatar);
        fitCamera();
        setProgress(100);
        setStatus('ready');
      },
      (event) => {
        if (event.total > 0) setProgress(Math.min(99, Math.round((event.loaded / event.total) * 100)));
      },
      () => {
        if (!disposed) setStatus('error');
      },
    );

    const render = (timestamp?: number) => {
      animationFrame = window.requestAnimationFrame(render);
      timer.update(timestamp);
      const elapsed = timer.getElapsed();
      if (avatar) {
        avatar.rotation.y = Math.sin(elapsed * 0.42) * (variant === 'companion' ? 0.08 : 0.035);
        avatar.position.y = Math.sin(elapsed * 0.8) * avatarSize.y * 0.006;
      }
      controls?.update();
      renderer.render(scene, camera);
    };
    render();

    return () => {
      disposed = true;
      window.cancelAnimationFrame(animationFrame);
      resizeObserver.disconnect();
      controls?.dispose();
      timer.dispose();
      if (avatar) {
        avatar.traverse((object) => {
          if (!(object instanceof THREE.Mesh)) return;
          object.geometry.dispose();
          const materials = Array.isArray(object.material) ? object.material : [object.material];
          materials.forEach(disposeMaterial);
        });
      }
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [variant]);

  return (
    <div ref={hostRef} className={`avatar-viewport avatar-viewport-${variant}`}>
      {status === 'loading' && <div className="avatar-viewport-state"><i/><span>正在载入临时分身 · {progress}%</span></div>}
      {status === 'error' && <div className="avatar-viewport-state error"><strong>E</strong><span>分身模型载入失败</span></div>}
    </div>
  );
}
