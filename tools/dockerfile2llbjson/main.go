package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/moby/buildkit/client/llb/sourceresolver"
	"github.com/moby/buildkit/frontend/dockerfile/dockerfile2llb"
	"github.com/moby/buildkit/frontend/dockerui"
	"github.com/moby/buildkit/solver/pb"
	digest "github.com/opencontainers/go-digest"
	specs "github.com/opencontainers/image-spec/specs-go/v1"
	"github.com/sirupsen/logrus"
)

type buildArgSlice map[string]string

func (s *buildArgSlice) String() string {
	return fmt.Sprintf("%v", *s)
}

func (s *buildArgSlice) Set(value string) error {
	parts := strings.SplitN(value, "=", 2)
	if len(parts) != 2 {
		return fmt.Errorf("expected key=value, got %s", value)
	}
	if *s == nil {
		*s = make(map[string]string)
	}
	(*s)[parts[0]] = parts[1]
	return nil
}

func (b buildArgSlice) ToMap() map[string]string { return b }

type OfflineResolver struct{}

func (r *OfflineResolver) ResolveImageConfig(ctx context.Context, ref string, opt sourceresolver.Opt) (string, digest.Digest, []byte, error) {
	emptydgst := digest.Digest("sha256:0000000000000000000000000000000000000000000000000000000000000000")
	img := &specs.Image{
		Platform: specs.Platform{
			Architecture: "amd64",
			OS:           "linux",
		},
		Config: specs.ImageConfig{
			Env:        []string{"PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"},
			Cmd:        []string{"/bin/sh"},
			WorkingDir: "/",
		},
		RootFS: specs.RootFS{
			Type: "layers",
			DiffIDs: []digest.Digest{
				emptydgst,
			},
		},
	}
	configJSON, err := json.Marshal(img)
	if err != nil {
		return "", "", nil, err
	}
	var dgst digest.Digest
	if strings.Contains(ref, "@sha256:") {
		parts := strings.Split(ref, "@")
		dgst = digest.Digest(parts[len(parts)-1])
	} else {
		dgst = emptydgst
	}
	return ref, dgst, configJSON, nil
}

func main() {
	logrus.SetLevel(logrus.WarnLevel)

	var output = flag.String("o", "", "output JSON file (default stdout)")
	var pretty = flag.Bool("p", false, "Pretty print JSON output")
	var verbose = flag.Bool("v", false, "Verbose output")
	var buildArgs buildArgSlice
	flag.Var(&buildArgs, "b", "Build argument in key=value format (can be repeated)")
	flag.Parse()

	if *verbose {
		logrus.SetLevel(logrus.DebugLevel)
	}

	df, err := io.ReadAll(os.Stdin)
	if err != nil {
		panic(err)
	}

	caps := pb.Caps.CapSet(pb.Caps.All())

	state, _, _, _, err := dockerfile2llb.Dockerfile2LLB(context.TODO(), df,
		dockerfile2llb.ConvertOpt{
			MetaResolver: &OfflineResolver{},
			LLBCaps:      &caps,
			SourceMap:    nil,
			Config: dockerui.Config{
				BuildArgs: buildArgs.ToMap(),
			},
		})
	if err != nil {
		panic(err)
	}

	def, err := state.Marshal(context.TODO())
	if err != nil {
		panic(err)
	}

	var ops []*pb.Op
	for _, dt := range def.Def {
		var op pb.Op
		if err := (&op).Unmarshal(dt); err != nil {
			panic(err)
		}
		ops = append(ops, &op)
	}

	var b []byte
	if *pretty {
		b, err = json.MarshalIndent(ops, "", "  ")
	} else {
		b, err = json.Marshal(ops)
	}
	if err != nil {
		panic(err)
	}

	if *output != "" {
		err = os.WriteFile(*output, b, 0644)
		if err != nil {
			panic(err)
		}
		return
	}
	_, err = os.Stdout.Write(b)
	if err != nil {
		panic(err)
	}
	_, err = os.Stdout.WriteString("\n")
	if err != nil {
		panic(err)
	}
}
