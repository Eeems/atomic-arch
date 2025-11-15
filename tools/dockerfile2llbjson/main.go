package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/moby/buildkit/client/llb/imagemetaresolver"
	"github.com/moby/buildkit/frontend/dockerfile/dockerfile2llb"
	"github.com/moby/buildkit/frontend/dockerui"
	"github.com/moby/buildkit/solver/pb"
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

func main() {
	logrus.SetLevel(logrus.WarnLevel)

	var output = flag.String("o", "", "output JSON file (default stdout)")
	var pretty = flag.Bool("p", false, "Pretty print JSON output")
	var buildArgs buildArgSlice
	flag.Var(&buildArgs, "b", "Build argument in key=value format (can be repeated)")
	flag.Parse()

	df, err := io.ReadAll(os.Stdin)
	if err != nil {
		panic(err)
	}

	caps := pb.Caps.CapSet(pb.Caps.All())
	state, _, _, _, err := dockerfile2llb.Dockerfile2LLB(context.TODO(), df,
		dockerfile2llb.ConvertOpt{
			MetaResolver: imagemetaresolver.Default(),
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
	if *output != "" {
		err := os.WriteFile(*output, b, 0644)
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
